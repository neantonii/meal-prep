"""Ingredient card renderer.

Turns an enriched ``meal_prep.models.ingredient.Ingredient`` into a standalone
HTML card, mirroring ``meal_prep.renderer`` (same dark theme, same f-string +
``_CSS`` pattern, no templates). Catalog data only: no provenance colors, no
photo. This is the presentation layer; it owns formatting and rounding.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import TYPE_CHECKING

from meal_prep.enums import Aisle
from meal_prep.models.ingredient import MacrosInfo
from meal_prep.renderer import _CSS, _macro_items, storage_display_name

if TYPE_CHECKING:
    from meal_prep.library import MealPrepLibrary
    from meal_prep.models.ingredient import Ingredient


def aisle_display_name(aisle: Aisle) -> str:
    """Human-facing aisle label for the ingredient card badge."""
    return aisle.value.capitalize()


def _conversion_rows(ingredient: Ingredient) -> str:
    """One row per authored conversion edge (deduped to the authored direction)."""
    seen: set[tuple[str, str]] = set()
    rows: list[str] = []
    for (source, target), factor in sorted(ingredient.conversion_graph.factors.items()):
        if (target, source) in seen:
            continue
        seen.add((source, target))
        if source == target:
            continue
        amount = int(factor) if factor == int(factor) else round(factor, 4)
        rows.append(
            f"<li>1 {html.escape(source)} = {amount} {html.escape(target)}</li>"
        )
    if not rows:
        return '<p class="storage-notes">No conversions authored.</p>'
    return '<ul class="facts">\n' + "\n".join(rows) + "\n</ul>"


def render_ingredient_card(ingredient: Ingredient) -> str:
    """Render one enriched ingredient into a standalone HTML card."""
    macros: MacrosInfo = ingredient.macros_per_100g
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(ingredient.name)} — Meal Prep Ingredient</title>
    <style>{_CSS}
    .facts {{ list-style: none; font-size: 0.9rem; }}
    .facts li {{ padding: 5px 0; border-bottom: 1px solid var(--border); }}
    .facts li:last-child {{ border-bottom: none; }}
    </style>
</head>
<body>
    <div class="container">
        <header class="recipe-header">
            <span class="recipe-category">{html.escape(aisle_display_name(ingredient.aisle))}</span>
            <h1 class="recipe-title">{html.escape(ingredient.name)}</h1>

            <div class="stats-grid">
                <div class="stat-box">
                    <div class="stat-label">Brand</div>
                    <div class="stat-val">{html.escape(ingredient.brand)}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Product</div>
                    <div class="stat-val">{html.escape(ingredient.product)}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Price</div>
                    <div class="stat-val success">${ingredient.price:.2f}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Package</div>
                    <div class="stat-val">{ingredient.package_weight_g:g} g</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Storage</div>
                    <div class="stat-val">{html.escape(storage_display_name(ingredient.storage))}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Shelf Life</div>
                    <div class="stat-val">{ingredient.shelf_life_days} days</div>
                </div>
            </div>
        </header>

        <section class="macro-banner">
            <div class="macro-banner-title">
                <span>⚡ Nutrition per 100g</span>
                <span>${ingredient.price_per_100g:.2f} / 100g</span>
            </div>
            <div class="macro-row">
{_macro_items(macros)}
            </div>
        </section>

        <div class="panel">
            <h2 class="panel-title">🔄 Conversions</h2>
            {_conversion_rows(ingredient)}
        </div>
    </div>
</body>
</html>
"""


def render_all_ingredient_cards(
    library: MealPrepLibrary, output_dir: Path | str
) -> list[Path]:
    """Render every catalog ingredient into ``output_dir/<aisle>/<slug>.html``.

    All cards are rendered to memory first; only then are stale ``*.html``
    files removed and fresh cards written.
    """
    target_root = Path(output_dir)
    if not target_root.is_dir():
        raise FileNotFoundError(f"output directory does not exist: {target_root}")

    rendered: list[tuple[Path, str]] = []
    for ingredient in library.catalog.values():
        target = target_root / ingredient.aisle.value / f"{ingredient.id}.html"
        rendered.append((target, render_ingredient_card(ingredient)))

    for stale in target_root.rglob("*.html"):
        stale.unlink()

    written: list[Path] = []
    for target, card in rendered:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(card, encoding="utf-8")
        written.append(target)
    return written
