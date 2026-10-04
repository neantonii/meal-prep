"""Ingredient draft review renderer.

Pipeline: staged entry YAML (``IngredientDTO`` shape) + provenance YAML
(``IngredientProvenance``) -> cross-check -> ``prepare_ingredient`` (gram
reachability, the real pipeline) -> standalone HTML review page. Values
come from the DTO, color from provenance, derived numbers from the
enriched ``Ingredient``; the page owns formatting only, like
``renderer.py``.

A DTO, provenance, or enrichment failure renders the errors instead of
values — the page can never show unvalidated numbers.

Usage (run from the repo root so data/ and src/ resolve):
    python .agents/skills/meal-ingredient/scripts/render_ingredient_review.py \\
        <draft.yaml> <provenance.yaml> <photo> <out.html>
"""

from __future__ import annotations

import base64
import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml
from ingredient_provenance import IngredientProvenance, Provenance, edge_key
from pydantic import ValidationError

from meal_prep.adapters.aisles import load_aisles
from meal_prep.adapters.units import load_units
from meal_prep.dtos.ingredient import IngredientDTO
from meal_prep.services.ingredients import prepare_ingredient

REPO_ROOT = Path(__file__).resolve().parents[4]

_CSS = """
:root { --bg: #0f172a; --surface: #1e293b; --border: #334155;
--text: #f8fafc; --muted: #94a3b8; --warn: #facc15; --err: #f87171;
--accent: #38bdf8; --ok: #4ade80; }
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
.sourced { color: var(--ok); }
.err { color: var(--err); }
.note { color: var(--muted); font-size: 0.85rem; margin-top: 10px; }
"""


def _conf_val(value: str, provenance: Provenance) -> str:
    """Inline value HTML by provenance: panel (plain), staged (yellow), usda (green)."""
    if provenance == Provenance.STAGED:
        return f'<span class="inferred">{html.escape(value)}</span>'
    if provenance == Provenance.USDA:
        return f'<span class="sourced">{html.escape(value)}</span>'
    return html.escape(value)


def _conf_fact(key: str, value: str, provenance: Provenance) -> str:
    """Render a fact by provenance: panel (plain), staged (yellow), usda (green)."""
    if provenance == Provenance.STAGED:
        val = f'<span class="inferred">{html.escape(value)}</span>'
    elif provenance == Provenance.USDA:
        val = f'<span class="sourced">{html.escape(value)}</span>'
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
    return "no package edge authored"


def _conversions_section(dto: IngredientDTO, provenance: IngredientProvenance) -> str:
    """List every staged conversion edge with its own provenance."""
    if not dto.conversions:
        return ""
    rows = "\n".join(
        _conf_fact(
            "Conversion",
            _edge_str(c.from_unit, c.to_unit, c.factor),
            provenance.conversions[edge_key(c.from_unit, c.to_unit)],
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


def render(dto: IngredientDTO, provenance: IngredientProvenance, photo_src: str) -> str:
    """Enrich via the real pipeline and render DTO + model as HTML.

    Values come from the DTO, color from provenance; the DTO feeds
    enrichment. ``provenance.check_against(dto)`` must pass first.
    """
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

    def _opt(v: float | None, prov: Provenance | None) -> tuple[str, Provenance] | None:
        if v is None or prov is None:
            return None
        return str(v), prov

    macros: list[tuple[Provenance, str, str, str]] = [
        (provenance.calories_kcal_provenance, str(m.calories_kcal), "kcal", "Calories"),
        (provenance.protein_g_provenance, str(m.protein_g), "g", "Protein"),
        (provenance.fat_g_provenance, str(m.fat_g), "g", "Fat"),
        (provenance.carbs_g_provenance, str(m.carbs_g), "g", "Carbs"),
        (provenance.fiber_g_provenance, str(m.fiber_g), "g", "Fiber"),
    ]
    for field, unit, label in [
        ("saturated_fat_g", "g", "Sat fat"),
        ("sugars_g", "g", "Sugars"),
        ("sodium_mg", "mg", "Sodium"),
        ("potassium_mg", "mg", "Potassium"),
    ]:
        opt = _opt(
            getattr(m, field),
            getattr(provenance, f"{field}_provenance"),
        )
        if opt is not None:
            value, prov = opt
            macros.append((prov, value, unit, label))
    macro_grid = (
        '<div class="macro-grid">\n'
        + "\n".join(
            f'<div class="macro"><div class="v">{_conf_val(v, prov)}'
            f' <span class="u">{html.escape(unit)}</span></div>'
            f'<div class="k">{html.escape(label)}</div></div>'
            for prov, v, unit, label in macros
        )
        + "\n</div>"
    )
    facts = [
        _conf_fact(
            "Aisle / storage",
            f"{dto.aisle} / {dto.storage.value}",
            provenance.aisle_provenance
            if provenance.aisle_provenance == provenance.storage_provenance
            else Provenance.STAGED,
        ),
        _conf_fact(
            "Shelf life",
            f"{dto.shelf_life_days} days",
            provenance.shelf_life_days_provenance,
        ),
    ]
    for field in ["id", "name", "step_name"]:
        facts.append(
            _conf_fact(
                field,
                getattr(dto, field),
                getattr(provenance, f"{field}_provenance"),
            )
        )
    facts_html = '<ul class="facts">\n' + "\n".join(facts) + "\n</ul>"
    conversions_html = _conversions_section(dto, provenance)

    package_provenance = next(
        (
            provenance.conversions[edge_key(c.from_unit, c.to_unit)]
            for c in dto.conversions
            if c.from_unit == "package"
        ),
        Provenance.STAGED,
    )
    head = (
        '<div class="card-head">\n'
        f'<div class="slug">{html.escape(dto.id)}</div>\n'
        f"<h1>{html.escape(dto.name)}</h1>\n"
        f'<div class="meta">{_conf_val(dto.reference.brand, provenance.brand_provenance)} · '
        f"{_conf_val(dto.reference.product, provenance.product_provenance)}</div>\n"
        f'<div class="meta">{_conf_val(f"${dto.reference.price:.2f}", provenance.price_provenance)} · '
        f"{_conf_val(_package_edge(dto), package_provenance)}</div>\n"
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


def _photo_data_uri(photo_path: str) -> str:
    """Embed photo bytes so the HTML is self-contained.

    A repo-relative `src` breaks wherever the preview panel does not serve
    the working tree; a data URI renders anywhere.
    """
    suffix = Path(photo_path).suffix.lower().lstrip(".") or "png"
    raw = Path(photo_path).read_bytes()
    return f"data:image/{suffix};base64,{base64.b64encode(raw).decode()}"


def main() -> int:
    draft_raw = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))
    prov_raw = yaml.safe_load(Path(sys.argv[2]).read_text(encoding="utf-8"))
    photo_src = _photo_data_uri(sys.argv[3])
    out = Path(sys.argv[4])
    try:
        dto = IngredientDTO.model_validate(draft_raw)
    except ValidationError as e:
        errs = [f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors()]
        out.write_text(_error_page("invalid draft", errs, photo_src), encoding="utf-8")
        print(f"draft errors: {errs}")
        return 1
    try:
        provenance = IngredientProvenance.model_validate(prov_raw)
    except ValidationError as e:
        errs = [f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors()]
        out.write_text(
            _error_page("invalid provenance", errs, photo_src), encoding="utf-8"
        )
        print(f"provenance errors: {errs}")
        return 1
    try:
        provenance.check_against(dto)
    except ValueError as e:
        out.write_text(
            _error_page("draft/provenance mismatch", [str(e)], photo_src),
            encoding="utf-8",
        )
        print(f"mismatch: {e}")
        return 1
    page = render(dto, provenance, photo_src)
    out.write_text(page, encoding="utf-8")
    print(f"review written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
