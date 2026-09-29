"""Recipe card renderer.

Turns an enriched ``meal_prep.models.recipe.Recipe`` into a standalone HTML
recipe card. This is the presentation layer: it owns formatting and rounding
(the enriched model keeps raw floats), and it re-scans the Cooklang instruction
text to turn ``@ingredient`` / ``#cookware`` / ``~timer`` tokens into styled
badges — reusing the exact compiled patterns from ``meal_prep.engines.cooklang``.

A ``Recipe`` is fully self-contained (it carries ``equipment_by_id``), so
``render_recipe_card`` takes only the recipe. ``render_all_recipe_cards`` loads a
``MealPrepLibrary``, prepares every recipe, and writes one card per recipe into
``<output_dir>/<category>/<slug>.html``.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import TYPE_CHECKING

from meal_prep.engines.cooklang import (
    COOKWARE_PATTERN,
    INGREDIENT_PATTERN,
    TIMER_PATTERN,
)
from meal_prep.models.recipe import Recipe

if TYPE_CHECKING:
    from meal_prep.library import MealPrepLibrary

_CSS = """
        :root {
            --bg: #0f172a;
            --surface: #1e293b;
            --surface-card: #273549;
            --border: #334155;
            --text: #f8fafc;
            --text-muted: #94a3b8;
            --primary: #38bdf8;
            --primary-bg: rgba(56, 189, 248, 0.12);
            --ing-color: #f59e0b;
            --ing-bg: rgba(245, 158, 11, 0.15);
            --cw-color: #06b6d4;
            --cw-bg: rgba(6, 182, 212, 0.15);
            --timer-color: #ec4899;
            --timer-bg: rgba(236, 72, 153, 0.15);
            --success: #10b981;
            --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            background-color: var(--bg);
            color: var(--text);
            font-family: var(--font);
            line-height: 1.6;
            padding: 24px 16px;
        }

        .container {
            max-width: 960px;
            margin: 0 auto;
        }

        /* Header Card */
        .recipe-header {
            background: linear-gradient(135deg, #1e293b 0%, #1e1b4b 100%);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 28px;
            margin-bottom: 24px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
        }

        .recipe-category {
            display: inline-block;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-weight: 700;
            color: var(--primary);
            background: var(--primary-bg);
            padding: 4px 10px;
            border-radius: 20px;
            margin-bottom: 12px;
            border: 1px solid rgba(56, 189, 248, 0.3);
        }

        .recipe-title {
            font-size: 2rem;
            font-weight: 800;
            margin-bottom: 16px;
            color: #ffffff;
            letter-spacing: -0.02em;
        }

        /* Quick Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
            gap: 12px;
            margin-top: 16px;
        }

        .stat-box {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 12px 14px;
            text-align: center;
        }

        .stat-label {
            font-size: 0.72rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 4px;
        }

        .stat-val {
            font-size: 1.15rem;
            font-weight: 700;
            color: #ffffff;
        }

        .stat-val.primary { color: var(--primary); }
        .stat-val.success { color: var(--success); }

        /* Macros Bar */
        .macro-banner {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 18px 24px;
            margin-bottom: 24px;
        }

        .macro-banner-title {
            font-size: 0.8rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--text-muted);
            margin-bottom: 12px;
            display: flex;
            justify-content: space-between;
        }

        .macro-row {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
            gap: 12px;
            text-align: center;
        }

        .macro-item {
            background: var(--surface-card);
            border-radius: 8px;
            padding: 10px 8px;
        }

        .macro-num {
            font-size: 1.3rem;
            font-weight: 800;
            color: #ffffff;
        }

        .macro-unit {
            font-size: 0.75rem;
            color: var(--text-muted);
        }

        .macro-tag {
            font-size: 0.75rem;
            font-weight: 600;
            margin-top: 2px;
            color: var(--primary);
        }

        /* Two-Column Layout */
        .content-grid {
            display: grid;
            grid-template-columns: 360px 1fr;
            gap: 24px;
        }

        @media (max-width: 840px) {
            .content-grid {
                grid-template-columns: 1fr;
            }
        }

        /* Panels */
        .panel {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 20px;
            margin-bottom: 20px;
        }

        .panel-title {
            font-size: 1.1rem;
            font-weight: 700;
            margin-bottom: 16px;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        /* Checklist */
        .ingredient-list {
            list-style: none;
        }

        .ingredient-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 10px 6px;
            border-bottom: 1px solid rgba(51, 65, 85, 0.6);
            transition: opacity 0.2s;
        }

        .ingredient-item:last-child {
            border-bottom: none;
        }

        .ingredient-checkbox-label {
            display: flex;
            align-items: center;
            cursor: pointer;
            user-select: none;
            flex: 1;
        }

        .ingredient-checkbox {
            margin-right: 12px;
            accent-color: var(--primary);
            width: 17px;
            height: 17px;
            cursor: pointer;
        }

        .ingredient-text {
            font-size: 0.95rem;
        }

        .ing-qty {
            font-weight: 700;
            color: var(--ing-color);
            margin-right: 6px;
        }

        .ing-meta {
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-left: 10px;
            white-space: nowrap;
        }

        /* Steps */
        .step-card {
            display: flex;
            gap: 16px;
            margin-bottom: 20px;
            padding: 16px;
            background: var(--surface-card);
            border: 1px solid rgba(51, 65, 85, 0.6);
            border-radius: 12px;
        }

        .step-num {
            font-size: 1.25rem;
            font-weight: 800;
            color: var(--primary);
            background: var(--primary-bg);
            width: 38px;
            height: 38px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            border: 1px solid rgba(56, 189, 248, 0.3);
        }

        .step-content {
            font-size: 0.98rem;
            line-height: 1.7;
            padding-top: 4px;
        }

        /* Cooklang Badges */
        .badge {
            display: inline-block;
            font-size: 0.85em;
            font-weight: 600;
            padding: 2px 7px;
            border-radius: 6px;
            margin: 0 2px;
            white-space: nowrap;
        }

        .badge-ingredient {
            color: var(--ing-color);
            background: var(--ing-bg);
            border: 1px solid rgba(245, 158, 11, 0.3);
        }

        .badge-cookware {
            color: var(--cw-color);
            background: var(--cw-bg);
            border: 1px solid rgba(6, 182, 212, 0.3);
        }

        .badge-timer {
            color: var(--timer-color);
            background: var(--timer-bg);
            border: 1px solid rgba(236, 72, 153, 0.3);
        }

        .storage-notes {
            font-size: 0.85rem;
            color: var(--text-muted);
            line-height: 1.5;
        }
"""


def _format_display_amount(quantity: float, unit: str) -> str:
    """Format a quantity + unit for display, dropping the reserved ``count`` noun.

    A count is just a number; appending the word "count" would be noise. Every
    other unit is shown verbatim (e.g. ``1 tbsp``).
    """
    if unit == "count":
        return f"{quantity:g}"
    return f"{quantity:g} {html.escape(unit)}"


def _format_step_text(
    text: str,
    ingredient_step_names: dict[str, str],
    ingredient_names: dict[str, str],
    ingredient_repeated: dict[str, bool],
    equipment_by_id: dict[str, str],
) -> str:
    """Render Cooklang instruction text into HTML with styled badges.

    The visible badge text uses the ingredient's ``step_name`` (prose-friendly
    short noun), while the ``title`` tooltip keeps the full canonical ``name``.

    Amounts are omitted from step badges by default — the shopping checklist is
    the single source of truth for quantities. The exception is an ingredient
    declared with an amount more than once (``repeated``): there the inline
    amount is needed to disambiguate the steps.
    """
    # Escape the authored prose up front so surrounding text (and any embedded
    # ``&``/``<``/``>``) is never emitted raw; the badge HTML injected below is
    # generated and separately escaped. Cooklang tokens use only ``@ # ~ { } %``
    # and word characters, so escaping does not disturb the patterns.
    text = html.escape(text)

    def replace_ingredient(match) -> str:
        if match.group(1):
            raw_id = match.group(1).strip().lower()
            qty = (match.group(2) or "").strip()
            unit = (match.group(3) or "").strip()
            step_name = ingredient_step_names.get(raw_id, raw_id)
            full_name = ingredient_names.get(raw_id, raw_id)
            if ingredient_repeated.get(raw_id, False):
                amount = f"{qty} {unit}".strip()
                label = f"{amount} {step_name}".strip()
            else:
                label = step_name
            return (
                f'<span class="badge badge-ingredient" title="Ingredient: {html.escape(full_name)}">'
                f'{html.escape(label)}</span>'
            )
        raw_id = match.group(4).strip().lower()
        step_name = ingredient_step_names.get(raw_id, raw_id)
        full_name = ingredient_names.get(raw_id, raw_id)
        return (
            f'<span class="badge badge-ingredient" title="Ingredient: {html.escape(full_name)}">'
            f'{html.escape(step_name)}</span>'
        )

    formatted = INGREDIENT_PATTERN.sub(replace_ingredient, text)

    def replace_cookware(match) -> str:
        raw_id = (match.group(1) or match.group(2)).strip().lower()
        name = equipment_by_id.get(raw_id, raw_id.replace("-", " ").title())
        return f'<span class="badge badge-cookware" title="Equipment: {html.escape(name)}">{html.escape(name)}</span>'

    formatted = COOKWARE_PATTERN.sub(replace_cookware, formatted)

    def replace_timer(match) -> str:
        name = (match.group(1) or "").strip()
        duration = match.group(2).strip()
        unit = match.group(3).strip()
        label = f"{duration} {unit}"
        if name:
            label = f"{label} ({name.replace('-', ' ')})"
        return f'<span class="badge badge-timer" title="Timer: {html.escape(label)}">⏱️ {html.escape(label)}</span>'

    formatted = TIMER_PATTERN.sub(replace_timer, formatted)

    paragraphs = [p.strip() for p in formatted.split("\n\n") if p.strip()]
    steps = []
    for index, paragraph in enumerate(paragraphs, 1):
        steps.append(
            f'<div class="step-card">\n'
            f'            <div class="step-num">{index}</div>\n'
            f'            <div class="step-content">{paragraph}</div>\n'
            f'        </div>'
        )
    return "\n\n".join(steps)


def _macro_item(value: str, unit: str, tag: str) -> str:
    return (
        f'<div class="macro-item">\n'
        f'            <div class="macro-num">{value}</div>\n'
        f'            <div class="macro-unit">{unit}</div>\n'
        f'            <div class="macro-tag">{tag}</div>\n'
        f'        </div>'
    )


def _macro_items(macros) -> str:
    items = [
        _macro_item(f"{macros.calories_kcal:.0f}", "kcal", "Calories"),
        _macro_item(f"{macros.protein_g:.1f}", "grams", "Protein"),
        _macro_item(f"{macros.fat_g:.1f}", "grams", "Total Fat"),
    ]
    if macros.saturated_fat_g > 0.05:
        items.append(_macro_item(f"{macros.saturated_fat_g:.1f}", "grams", "Sat Fat"))
    items.append(_macro_item(f"{macros.carbs_g:.1f}", "grams", "Total Carbs"))
    if macros.fiber_g > 0.05:
        items.append(_macro_item(f"{macros.fiber_g:.1f}", "grams", "Fiber"))
    if macros.sugars_g > 0.05:
        items.append(_macro_item(f"{macros.sugars_g:.1f}", "grams", "Sugars"))
    if macros.sodium_mg > 0:
        items.append(_macro_item(f"{macros.sodium_mg:.0f}", "mg", "Sodium"))
    if macros.potassium_mg > 0:
        items.append(_macro_item(f"{macros.potassium_mg:.0f}", "mg", "Potassium"))
    return "\n".join(items)


def render_recipe_card(recipe: Recipe) -> str:
    """Render one enriched recipe into a standalone HTML card."""
    cat_label = recipe.category.value.replace("_", " ").title()
    portion_g = recipe.portion_cooked_g
    serving_macros = recipe.per_serving_macros
    batch_macros = recipe.batch_macros

    ingredient_names = {item.id: item.name for item in recipe.ingredients}
    ingredient_step_names = {item.id: item.step_name for item in recipe.ingredients}
    ingredient_repeated = {item.id: item.repeated for item in recipe.ingredients}

    ingredient_rows = []
    for item in recipe.ingredients:
        ingredient_rows.append(
            f'<li class="ingredient-item">\n'
            f'            <label class="ingredient-checkbox-label">\n'
            f'                <input type="checkbox" class="ingredient-checkbox">\n'
            f'                <span class="checkmark"></span>\n'
            f'                <span class="ingredient-text">\n'
            f'                    <span class="ing-qty">{_format_display_amount(item.quantity, item.unit)}</span>\n'
            f'                    <span class="ing-name">{html.escape(item.name)}</span>\n'
            f'                </span>\n'
            f'            </label>\n'
            f'            <span class="ing-meta">{item.grams:.1f}g · ${item.cost:.2f} · {item.macros.calories_kcal:.0f} kcal</span>\n'
            f'        </li>'
        )
    ingredients_html = "\n\n".join(ingredient_rows)

    equipment_badges = " ".join(
        f'<span class="badge badge-cookware">{html.escape(name)}</span>' for name in recipe.equipment
    )

    steps_html = _format_step_text(
        recipe.instructions,
        ingredient_step_names,
        ingredient_names,
        ingredient_repeated,
        dict(recipe.equipment_by_id),
    )

    freezer_badge = "❄️ Freezer Friendly" if recipe.freezer_friendly else "🚫 No Freezing"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(recipe.title)} — Meal Prep Recipe</title>
    <style>{_CSS}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header class="recipe-header">
            <span class="recipe-category">{html.escape(cat_label)}</span>
            <h1 class="recipe-title">{html.escape(recipe.title)}</h1>

            <div class="stats-grid">
                <div class="stat-box">
                    <div class="stat-label">Servings</div>
                    <div class="stat-val primary">{recipe.servings:g} meals</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Portion (Cooked)</div>
                    <div class="stat-val">{portion_g:g} g</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Cost / Portion</div>
                    <div class="stat-val success">${recipe.cost_per_portion:.2f}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Safe Fridge</div>
                    <div class="stat-val">{recipe.fridge_days} days</div>
                </div>
            </div>
        </header>

        <!-- Macros Banner -->
        <section class="macro-banner">
            <div class="macro-banner-title">
                <span>⚡ Per-Serving Nutrition ({portion_g:g}g cooked)</span>
                <span>Total Batch: {batch_macros.calories_kcal:.0f} kcal · {batch_macros.protein_g:.0f}g P</span>
            </div>
            <div class="macro-row">
{_macro_items(serving_macros)}
            </div>
        </section>

        <!-- Main Content -->
        <div class="content-grid">
            <!-- Left Column: Ingredients & Equipment -->
            <aside class="sidebar">
                <div class="panel">
                    <h2 class="panel-title">
                        <span>🛒 Ingredients</span>
                        <span style="font-size: 0.8rem; font-weight: 500; color: var(--text-muted);">{len(recipe.ingredients)} items</span>
                    </h2>
                    <ul class="ingredient-list">
                        {ingredients_html}
                    </ul>
                    <div style="margin-top: 14px; padding-top: 10px; border-top: 1px solid var(--border); font-size: 0.82rem; color: var(--text-muted); display: flex; justify-content: space-between;">
                        <span>Raw Batch Weight:</span>
                        <strong style="color: #fff;">{recipe.batch_g:.1f} g</strong>
                    </div>
                    <div style="margin-top: 4px; font-size: 0.82rem; color: var(--text-muted); display: flex; justify-content: space-between;">
                        <span>Total Batch Cost:</span>
                        <strong style="color: var(--success);">${recipe.total_cost:.2f} CAD</strong>
                    </div>
                </div>

                <div class="panel">
                    <h2 class="panel-title">🍳 Equipment</h2>
                    <div style="display: flex; flex-wrap: wrap; gap: 8px;">
                        {equipment_badges}
                    </div>
                </div>

                <div class="panel">
                    <h2 class="panel-title">📦 Storage</h2>
                    <p class="storage-notes">
                        <strong>Fridge:</strong> Safe up to <strong>{recipe.fridge_days} days</strong> in an airtight container.<br>
                        <strong>Freezer:</strong> {freezer_badge}.
                    </p>
                </div>
            </aside>

            <!-- Right Column: Step-by-Step Instructions -->
            <main class="main-content">
                <div class="panel">
                    <h2 class="panel-title">👨‍🍳 Cooking Instructions</h2>
                    {steps_html}
                </div>
            </main>
        </div>
    </div>
</body>
</html>
"""


def render_all_recipe_cards(library: "MealPrepLibrary", output_dir: Path | str) -> list[Path]:
    """Render every recipe in ``library`` into ``output_dir/<category>/<slug>.html``.

    The output directory is force-cleaned first: any pre-existing ``*.html`` file
    under ``output_dir`` is removed before regeneration, so stale cards for
    recipes that no longer exist (e.g. a deleted ``.cook`` file) never linger.
    """
    from meal_prep.services.recipes import prepare_recipe

    target_root = Path(output_dir)

    # Force cleanup: drop every stale card before regenerating.
    for stale in target_root.rglob("*.html"):
        stale.unlink()

    written: list[Path] = []
    for recipe_id, dto in library.recipes.items():
        prepared = prepare_recipe(dto, library.catalog, library.equipment)
        category_dir = target_root / prepared.category.value
        category_dir.mkdir(parents=True, exist_ok=True)
        target = category_dir / f"{prepared.id}.html"
        target.write_text(render_recipe_card(prepared), encoding="utf-8")
        written.append(target)
    return written
