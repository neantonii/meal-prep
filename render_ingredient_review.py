"""Ingredient draft review renderer.

Pipeline: recognizer JSON -> ``IngredientDTO`` (shape validation) ->
``prepare_ingredient`` (gram reachability, the real pipeline) -> standalone
HTML review page. The page renders strictly from the DTO (authored basis)
and the enriched ``Ingredient`` (derived per-100g, package weight, pricing);
it owns formatting only, like ``renderer.py``.

Unknown identity facts (name, aisle, storage, ...) arrive as ``TODO(user)``
placeholders and render as NEEDS-USER rows. A DTO that fails shape
validation, or a model that fails enrichment, renders the errors instead of
values — the page can never show unvalidated numbers.

Usage:
    python render_ingredient_review.py <recognizer.json> <photo> <out.html>
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from pydantic import ValidationError

from meal_prep.adapters.aisles import load_aisles
from meal_prep.adapters.units import load_units
from meal_prep.dtos.ingredient import IngredientDTO
from meal_prep.services.ingredients import prepare_ingredient

REPO_ROOT = Path(__file__).resolve().parent

_CSS = """
:root { --bg: #0f172a; --surface: #1e293b; --border: #334155;
--text: #f8fafc; --muted: #94a3b8; --warn: #facc15; --err: #f87171;
--accent: #38bdf8; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--text);
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
line-height: 1.5; padding: 24px 16px; }
.container { max-width: 720px; margin: 0 auto; }
.card-head { background: linear-gradient(135deg, #1e293b 0%, #1e1b4b 100%);
border: 1px solid var(--border); border-radius: 16px; padding: 24px;
margin-bottom: 16px; }
.card-head .slug { color: var(--accent); font-family: monospace; font-size: 0.85rem; }
.card-head h1 { font-size: 1.5rem; margin: 4px 0; }
.card-head .meta { color: var(--muted); font-size: 0.9rem; }
.panel { background: var(--surface); border: 1px solid var(--border);
border-radius: 12px; padding: 18px; margin-bottom: 16px; }
.panel h2 { font-size: 1.05rem; margin-bottom: 12px; }
.panel .basis { color: var(--muted); font-size: 0.85rem; margin-bottom: 10px; }
.photo { max-width: 100%; border-radius: 8px; border: 1px solid var(--border); }
.macro-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.macro { background: var(--bg); border: 1px solid var(--border);
border-radius: 10px; padding: 10px 12px; }
.macro .v { font-size: 1.25rem; font-weight: 700; }
.macro .u { font-size: 0.8rem; color: var(--muted); }
.macro .k { font-size: 0.8rem; color: var(--muted); }
.facts { list-style: none; font-size: 0.9rem; }
.facts li { padding: 5px 0; border-bottom: 1px solid var(--border); }
.facts li:last-child { border-bottom: none; }
.facts .k { color: var(--muted); }
.inferred { color: var(--warn); }
.missing { color: var(--err); font-weight: 700; }
.err { color: var(--err); }
.note { color: var(--muted); font-size: 0.85rem; margin-top: 10px; }
"""


def _macro(value: str, unit: str, label: str) -> str:
    return (
        f'<div class="macro"><div class="v">{html.escape(value)}'
        f' <span class="u">{html.escape(unit)}</span></div>'
        f'<div class="k">{html.escape(label)}</div></div>'
    )


def _conf_val(value: str, confidence: str) -> str:
    """Inline value HTML by provenance: panel (plain), inferred (yellow), missing (red)."""
    if confidence == "inferred":
        return f'<span class="inferred">{html.escape(value)}</span>'
    if confidence == "missing":
        return f'<span class="missing">{html.escape(value)}</span>'
    return html.escape(value)


def _need_fact(key: str, why: str) -> str:
    return (
        f'<li><span class="k">{html.escape(key)}:</span> '
        f'<span class="missing">TODO(user)</span> — {html.escape(why)}</li>'
    )


def _conf_fact(key: str, value: str, confidence: str) -> str:
    """Render a fact by provenance: panel (plain), inferred (yellow), missing (red)."""
    if confidence == "inferred":
        val = f'<span class="inferred">{html.escape(value)}</span>'
    elif confidence == "missing":
        val = f'<span class="missing">{html.escape(value)} (unsure — your fact needed)</span>'
    else:
        val = html.escape(value)
    return f'<li><span class="k">{html.escape(key)}:</span> {val}</li>'


def _edge_str(from_unit: str, to_unit: str, factor: float) -> str:
    amount = int(factor) if factor == int(factor) else factor
    return f"1 {from_unit} = {amount} {to_unit}"


def _package_edge(dto: IngredientDTO) -> str:
    for c in dto.conversions:
        if c.from_unit == "package":
            amount = int(c.factor) if c.factor == int(c.factor) else c.factor
            return f"{amount} {c.to_unit}"
    return "TODO(user) — no package edge authored"


def _edge_confidence(raw: dict, from_unit: str, to_unit: str, default: str) -> str:
    """Per-edge provenance from the authoring-only `guessed_edges` list.

    Never touches the DTO: `guessed_edges` lives beside `conversions` in the
    draft JSON and is stripped before validation. Listed edges render inferred.
    """
    for e in raw.get("guessed_edges", []):
        if e.get("from") == from_unit and e.get("to") == to_unit:
            return "inferred"
    return default


def _conversions_section(dto: IngredientDTO, raw: dict) -> str:
    """List every authored conversion edge; empty string when none."""
    if not dto.conversions:
        return ""
    default = provenance(raw, "conversions")
    rows = "\n".join(
        _conf_fact(
            "Conversion",
            _edge_str(c.from_unit, c.to_unit, c.factor),
            _edge_confidence(raw, c.from_unit, c.to_unit, default),
        )
        for c in dto.conversions
    )
    return _panel("Conversions", "", f'<ul class="facts">\n{rows}\n</ul>')


def _basis_subline(unit: str, amount: float, basis_g: float | None) -> str:
    subline = f"per {amount:g} {unit}"
    if basis_g is not None:
        subline += f" ({basis_g:g} g)"
    return subline


def _panel(title: str, sub: str, body: str) -> str:
    sub_html = f'<p class="basis">{html.escape(sub)}</p>' if sub else ""
    return f'<div class="panel"><h2>{html.escape(title)}</h2>\n{sub_html}{body}</div>'


def _error_page(title: str, errors: list[str], photo: str) -> str:
    items = "\n".join(f'<p class="err">- {html.escape(e)}</p>' for e in errors)
    return (
        "<!DOCTYPE html>\n<html><head><meta charset='UTF-8'>"
        f"<title>Label review — {html.escape(title)}</title>"
        f"<style>{_CSS}</style></head><body><div class='container'>"
        f"<h1>Label review — {html.escape(title)}</h1>"
        f'<div class="panel"><h2>Original label</h2>\n<img class="photo" src="{html.escape(photo)}"></div>'
        f'<div class="panel"><h2>Validation errors</h2>\n{items}</div>'
        "</div></body></html>"
    )


PANEL_KEYS = {
    "brand",
    "product",
    "price",
    "calories_kcal",
    "protein_g",
    "fat_g",
    "carbs_g",
    "fiber_g",
    "saturated_fat_g",
    "sugars_g",
    "sodium_mg",
    "potassium_mg",
    "basis",
    "conversions",
}

IDENTITY_DEFAULTS = {
    "id": "slug it in chat",
    "name": "label-style noun",
    "step_name": "prose noun",
    "aisle": "confirm aisle",
    "storage": "confirm storage",
    "shelf_life_days": "days under this storage",
    "brand": "from panel or chat",
    "product": "full commercial name",
    "price": "CAD, your fact",
}


def provenance(raw: dict, key: str) -> str:
    """Where a draft field came from: panel, inferred, or missing."""
    if key in raw:
        return "panel" if key in PANEL_KEYS else "inferred"
    return "missing"


def build_dto(raw: dict) -> IngredientDTO:
    """Shape recognizer output into an IngredientDTO; unknowns stay TODO(user)."""
    basis = raw.get("basis", {})
    macros = {
        "unit": basis.get("unit", "g"),
        "amount": basis.get("amount", 100),
        "calories_kcal": raw.get("calories_kcal", 0),
        "protein_g": raw.get("protein_g", 0),
        "fat_g": raw.get("fat_g", 0),
        "carbs_g": raw.get("carbs_g", 0),
        "fiber_g": raw.get("fiber_g", 0),
        "saturated_fat_g": raw.get("saturated_fat_g"),
        "sugars_g": raw.get("sugars_g"),
        "sodium_mg": raw.get("sodium_mg"),
        "potassium_mg": raw.get("potassium_mg"),
    }
    return IngredientDTO.model_validate(
        {
            "id": raw.get("id", "TODO(user)"),
            "name": raw.get("name", "TODO(user)"),
            "step_name": raw.get("step_name", "TODO(user)"),
            "aisle": raw.get("aisle", "pantry"),
            "storage": raw.get("storage", "ambient"),
            "shelf_life_days": raw.get("shelf_life_days", 1),
            "reference": {
                "brand": raw.get("brand", "TODO(user)"),
                "product": raw.get("product", "TODO(user)"),
                "price": raw.get("price", 0.01),
            },
            "macros": macros,
            "custom_units": raw.get("custom_units", {}),
            "conversions": raw.get("conversions", []),
        }
    )


def render(dto: IngredientDTO, raw: dict, photo_src: str) -> str:
    """Enrich via the real pipeline and render DTO + model as HTML."""
    units = load_units(REPO_ROOT / "data" / "units.yaml")
    aisles = {a.id: a for a in load_aisles(REPO_ROOT / "data" / "aisles.yaml")}
    try:
        ing = prepare_ingredient(dto, units, aisles)
    except ValueError as e:
        return _error_page(dto.id, [str(e)], photo_src)

    m = dto.macros
    basis_g = (
        ing.convert(m.amount, m.unit, "g")
        if m.unit != "g" and ing.can_convert(m.unit, "g")
        else None
    )

    def _opt(v: float | None) -> str | None:
        return None if v is None else str(v)

    macros = [
        ("calories_kcal", str(m.calories_kcal), "kcal", "Calories"),
        ("protein_g", str(m.protein_g), "g", "Protein"),
        ("fat_g", str(m.fat_g), "g", "Fat"),
        ("carbs_g", str(m.carbs_g), "g", "Carbs"),
        ("fiber_g", str(m.fiber_g), "g", "Fiber"),
        ("saturated_fat_g", _opt(m.saturated_fat_g), "g", "Sat fat"),
        ("sugars_g", _opt(m.sugars_g), "g", "Sugars"),
        ("sodium_mg", _opt(m.sodium_mg), "mg", "Sodium"),
        ("potassium_mg", _opt(m.potassium_mg), "mg", "Potassium"),
    ]
    macro_grid = (
        '<div class="macro-grid">\n'
        + "\n".join(_macro(v, u, label) for _, v, u, label in macros if v is not None)
        + "\n</div>"
    )
    facts = [
        _conf_fact(
            "Aisle / storage",
            f"{dto.aisle} / {dto.storage}",
            provenance(raw, "aisle")
            if provenance(raw, "aisle") == provenance(raw, "storage")
            else "inferred",
        ),
        _conf_fact(
            "Shelf life",
            f"{dto.shelf_life_days} days",
            provenance(raw, "shelf_life_days"),
        ),
    ]
    for field in ["id", "name", "step_name"]:
        val = getattr(dto, field)
        conf = provenance(raw, field)
        if "TODO" in val:
            facts.append(_need_fact(field, IDENTITY_DEFAULTS[field]))
        else:
            facts.append(_conf_fact(field, val, conf))
    facts_html = '<ul class="facts">\n' + "\n".join(facts) + "\n</ul>"
    conversions_html = _conversions_section(dto, raw)

    head = (
        '<div class="card-head">\n'
        f'<div class="slug">{html.escape(dto.id)}</div>\n'
        f"<h1>{html.escape(dto.name)}</h1>\n"
        f'<div class="meta">{_conf_val(dto.reference.brand, provenance(raw, "brand"))} · '
        f"{_conf_val(dto.reference.product, provenance(raw, 'product'))}</div>\n"
        f'<div class="meta">{_conf_val(f"${dto.reference.price:.2f}", provenance(raw, "price"))} · '
        f"{_conf_val(_package_edge(dto), provenance(raw, 'conversions'))}</div>\n"
        "</div>"
    )
    return (
        "<!DOCTYPE html>\n<html><head><meta charset='UTF-8'>"
        f"<title>{html.escape(dto.name)}</title>"
        f"<style>{_CSS}</style></head><body><div class='container'>"
        f"{head}"
        f'<div class="panel"><img class="photo" src="{html.escape(photo_src)}"></div>'
        f"{_panel('Nutrition', _basis_subline(m.unit, m.amount, basis_g), macro_grid)}"
        f"{_panel('Details', '', facts_html)}"
        f"{conversions_html}"
        "</div></body></html>"
    )


def main() -> int:
    raw = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    photo_src, out = sys.argv[2], Path(sys.argv[3])
    try:
        dto = build_dto(raw)
    except ValidationError as e:
        errs = [f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors()]
        out.write_text(_error_page("invalid DTO", errs, photo_src), encoding="utf-8")
        print(f"DTO errors: {errs}")
        return 1
    page = render(dto, raw, photo_src)
    out.write_text(page, encoding="utf-8")
    print(f"review written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
