"""Recipe Card Renderer.

Renders .cook recipes into clean, responsive HTML recipe cards with Cooklang-style
inline badges, ingredient checklists, macro summaries, yield, storage, and equipment metadata.
"""

from pathlib import Path
from typing import Any, TYPE_CHECKING
from meal_prep.models.recipe import Recipe
from meal_prep.models.ingredient import Ingredient
from meal_prep.models.equipment import EquipmentRegistry
from meal_prep.engines.cooklang import COOKWARE_PATTERN, INGREDIENT_PATTERN, TIMER_PATTERN
from meal_prep.models.units import UnitsRegistry
from meal_prep.calculator import PreparedRecipe


def _format_step_text(
    text: str,
    catalog_or_names: dict[str, Ingredient] | dict[str, str],
    equipment: EquipmentRegistry | None = None,
) -> str:
    """Format Cooklang instructions into HTML with styled badges."""
    # Format ingredients: @id{qty%unit} or @id
    def replace_ing(m):
        if m.group(1):
            raw_id = m.group(1).strip().lower()
            qty = m.group(2).strip() if m.group(2) else ""
            unit = m.group(3).strip() if m.group(3) else ""
            item = catalog_or_names.get(raw_id)
            display_name = item.name if hasattr(item, "name") else (item or raw_id)
            if qty and unit:
                label = f"{qty} {unit} {display_name}"
            elif qty:
                label = f"{qty} {display_name}"
            else:
                label = display_name
            return f'<span class="badge badge-ingredient" title="Ingredient: {display_name}">{label}</span>'
        else:
            raw_id = m.group(4).strip().lower()
            item = catalog_or_names.get(raw_id)
            display_name = item.name if hasattr(item, "name") else (item or raw_id)
            return f'<span class="badge badge-ingredient">{display_name}</span>'

    ing_pattern = INGREDIENT_PATTERN
    formatted = ing_pattern.sub(replace_ing, text)

    # Format cookware: #id{} or #id
    def replace_cw(m):
        raw_id = (m.group(1) or m.group(2)).strip().lower()
        eq_item = equipment.get(raw_id) if equipment is not None else None
        display_name = eq_item.name if eq_item else raw_id.replace("-", " ").title()
        return f'<span class="badge badge-cookware" title="Equipment: {display_name}">{display_name}</span>'

    cw_pattern = COOKWARE_PATTERN
    formatted = cw_pattern.sub(replace_cw, formatted)

    # Format timers: ~name{duration%unit} or ~{duration%unit}
    def replace_timer(m):
        name = (m.group(1) or "").strip()
        dur = m.group(2).strip()
        unit = m.group(3).strip()
        label = f"{dur} {unit}"
        if name:
            label = f"{label} ({name.replace('-', ' ')})"
        return f'<span class="badge badge-timer" title="Timer: {label}">⏱️ {label}</span>'

    timer_pattern = TIMER_PATTERN
    formatted = timer_pattern.sub(replace_timer, formatted)

    # Split into paragraphs / steps
    paragraphs = [p.strip() for p in formatted.split("\n\n") if p.strip()]
    step_items = []
    for idx, p in enumerate(paragraphs, 1):
        step_items.append(f"""
        <div class="step-card">
            <div class="step-num">{idx}</div>
            <div class="step-content">{p}</div>
        </div>
        """)

    return "\n".join(step_items)


def render_recipe_card_html(
    recipe_or_prepared: Recipe | PreparedRecipe,
    catalog: dict[str, Ingredient] | None = None,
    equipment: EquipmentRegistry | None = None,
    units: UnitsRegistry | None = None,
) -> str:
    """Generate a self-contained, responsive HTML recipe card from precomputed PreparedRecipe data."""
    if isinstance(recipe_or_prepared, PreparedRecipe):
        prepared = recipe_or_prepared
    else:
        if catalog is None or units is None:
            raise ValueError("catalog and units must be provided when passing a raw Recipe object")
        from meal_prep.calculator import prepare_recipe
        prepared = prepare_recipe(recipe_or_prepared, catalog, units, equipment)

    recipe = prepared.recipe
    batch_macros = prepared.batch_macros
    serv_macros = prepared.serving_macros
    batch_cost = prepared.batch_cost
    serv_cost = prepared.serving_cost
    raw_g = prepared.raw_batch_weight_g
    loss = prepared.cooking_loss_percent
    safe_days = prepared.safe_fridge_days
    portion_g = prepared.portion_cooked_weight_g
    cat_label = recipe.category.value.replace("_", " ").title()

    # Format ingredients checklist directly from prepared data
    ing_rows = []
    for item in prepared.ingredients:
        qty_str = f"{item.quantity:g}"
        ing_rows.append(f"""
        <li class="ingredient-item">
            <label class="ingredient-checkbox-label">
                <input type="checkbox" class="ingredient-checkbox">
                <span class="checkmark"></span>
                <span class="ingredient-text">
                    <span class="ing-qty">{qty_str} {item.unit}</span>
                    <span class="ing-name">{item.name}</span>
                </span>
            </label>
            <span class="ing-meta">{item.detail_text}</span>
        </li>
        """)
    ingredients_html = "\n".join(ing_rows)

    # Format equipment list directly from prepared data
    eq_badges = [
        f'<span class="badge badge-cookware">{name}</span>'
        for name in prepared.equipment_names
    ]
    equipment_html = " ".join(eq_badges)

    # Format steps
    ingredient_name_map = {item.id: item.name for item in prepared.ingredients}
    steps_html = _format_step_text(recipe.instructions, ingredient_name_map, equipment)

    freezer_badge = "❄️ Freezer Friendly" if prepared.freezer_friendly else "🚫 No Freezing"

    # Build dynamic macro items
    macro_items = [
        f"""<div class="macro-item">
            <div class="macro-num">{serv_macros.calories_kcal:.0f}</div>
            <div class="macro-unit">kcal</div>
            <div class="macro-tag">Calories</div>
        </div>""",
        f"""<div class="macro-item">
            <div class="macro-num">{serv_macros.protein_g:.1f}</div>
            <div class="macro-unit">grams</div>
            <div class="macro-tag">Protein</div>
        </div>""",
        f"""<div class="macro-item">
            <div class="macro-num">{serv_macros.fat_g:.1f}</div>
            <div class="macro-unit">grams</div>
            <div class="macro-tag">Total Fat</div>
        </div>""",
    ]

    if (serv_macros.saturated_fat_g or 0) > 0.05:
        macro_items.append(f"""<div class="macro-item">
            <div class="macro-num">{serv_macros.saturated_fat_g:.1f}</div>
            <div class="macro-unit">grams</div>
            <div class="macro-tag">Sat Fat</div>
        </div>""")

    macro_items.append(f"""<div class="macro-item">
        <div class="macro-num">{serv_macros.carbs_g:.1f}</div>
        <div class="macro-unit">grams</div>
        <div class="macro-tag">Total Carbs</div>
    </div>""")

    if (serv_macros.fiber_g or 0) > 0.05:
        macro_items.append(f"""<div class="macro-item">
            <div class="macro-num">{serv_macros.fiber_g:.1f}</div>
            <div class="macro-unit">grams</div>
            <div class="macro-tag">Fiber</div>
        </div>""")

    if (serv_macros.sugars_g or 0) > 0.05:
        macro_items.append(f"""<div class="macro-item">
            <div class="macro-num">{serv_macros.sugars_g:.1f}</div>
            <div class="macro-unit">grams</div>
            <div class="macro-tag">Sugars</div>
        </div>""")

    if (serv_macros.sodium_mg or 0) > 0:
        macro_items.append(f"""<div class="macro-item">
            <div class="macro-num">{serv_macros.sodium_mg:.0f}</div>
            <div class="macro-unit">mg</div>
            <div class="macro-tag">Sodium</div>
        </div>""")

    if (serv_macros.potassium_mg or 0) > 0:
        macro_items.append(f"""<div class="macro-item">
            <div class="macro-num">{serv_macros.potassium_mg:.0f}</div>
            <div class="macro-unit">mg</div>
            <div class="macro-tag">Potassium</div>
        </div>""")

    macro_boxes_html = "\n".join(macro_items)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{recipe.title} — Meal Prep Recipe</title>
    <style>
        :root {{
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
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            background-color: var(--bg);
            color: var(--text);
            font-family: var(--font);
            line-height: 1.6;
            padding: 24px 16px;
        }}

        .container {{
            max-width: 960px;
            margin: 0 auto;
        }}

        /* Header Card */
        .recipe-header {{
            background: linear-gradient(135deg, #1e293b 0%, #1e1b4b 100%);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 28px;
            margin-bottom: 24px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
        }}

        .recipe-category {{
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
        }}

        .recipe-title {{
            font-size: 2rem;
            font-weight: 800;
            margin-bottom: 16px;
            color: #ffffff;
            letter-spacing: -0.02em;
        }}

        /* Quick Stats Grid */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
            gap: 12px;
            margin-top: 16px;
        }}

        .stat-box {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 12px 14px;
            text-align: center;
        }}

        .stat-label {{
            font-size: 0.72rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 4px;
        }}

        .stat-val {{
            font-size: 1.15rem;
            font-weight: 700;
            color: #ffffff;
        }}

        .stat-val.primary {{ color: var(--primary); }}
        .stat-val.success {{ color: var(--success); }}

        /* Macros Bar */
        .macro-banner {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 18px 24px;
            margin-bottom: 24px;
        }}

        .macro-banner-title {{
            font-size: 0.8rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--text-muted);
            margin-bottom: 12px;
            display: flex;
            justify-content: space-between;
        }}

        .macro-row {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
            gap: 12px;
            text-align: center;
        }}

        .macro-item {{
            background: var(--surface-card);
            border-radius: 8px;
            padding: 10px 8px;
        }}

        .macro-num {{
            font-size: 1.3rem;
            font-weight: 800;
            color: #ffffff;
        }}

        .macro-unit {{
            font-size: 0.75rem;
            color: var(--text-muted);
        }}

        .macro-tag {{
            font-size: 0.75rem;
            font-weight: 600;
            margin-top: 2px;
            color: var(--primary);
        }}

        /* Two-Column Layout */
        .content-grid {{
            display: grid;
            grid-template-columns: 360px 1fr;
            gap: 24px;
        }}

        @media (max-width: 840px) {{
            .content-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        /* Panels */
        .panel {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 20px;
            margin-bottom: 20px;
        }}

        .panel-title {{
            font-size: 1.1rem;
            font-weight: 700;
            margin-bottom: 16px;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}

        /* Checklist */
        .ingredient-list {{
            list-style: none;
        }}

        .ingredient-item {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 10px 6px;
            border-bottom: 1px solid rgba(51, 65, 85, 0.6);
            transition: opacity 0.2s;
        }}

        .ingredient-item:last-child {{
            border-bottom: none;
        }}

        .ingredient-checkbox-label {{
            display: flex;
            align-items: center;
            cursor: pointer;
            user-select: none;
            flex: 1;
        }}

        .ingredient-checkbox {{
            margin-right: 12px;
            accent-color: var(--primary);
            width: 17px;
            height: 17px;
            cursor: pointer;
        }}

        .ingredient-text {{
            font-size: 0.95rem;
        }}

        .ing-qty {{
            font-weight: 700;
            color: var(--ing-color);
            margin-right: 6px;
        }}

        .ing-meta {{
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-left: 10px;
            white-space: nowrap;
        }}

        /* Steps */
        .step-card {{
            display: flex;
            gap: 16px;
            margin-bottom: 20px;
            padding: 16px;
            background: var(--surface-card);
            border: 1px solid rgba(51, 65, 85, 0.6);
            border-radius: 12px;
        }}

        .step-num {{
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
        }}

        .step-content {{
            font-size: 0.98rem;
            line-height: 1.7;
            padding-top: 4px;
        }}

        /* Cooklang Badges */
        .badge {{
            display: inline-block;
            font-size: 0.85em;
            font-weight: 600;
            padding: 2px 7px;
            border-radius: 6px;
            margin: 0 2px;
            white-space: nowrap;
        }}

        .badge-ingredient {{
            color: var(--ing-color);
            background: var(--ing-bg);
            border: 1px solid rgba(245, 158, 11, 0.3);
        }}

        .badge-cookware {{
            color: var(--cw-color);
            background: var(--cw-bg);
            border: 1px solid rgba(6, 182, 212, 0.3);
        }}

        .badge-timer {{
            color: var(--timer-color);
            background: var(--timer-bg);
            border: 1px solid rgba(236, 72, 153, 0.3);
        }}

        .storage-notes {{
            font-size: 0.85rem;
            color: var(--text-muted);
            line-height: 1.5;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header class="recipe-header">
            <span class="recipe-category">{cat_label}</span>
            <h1 class="recipe-title">{recipe.title}</h1>
            
            <div class="stats-grid">
                <div class="stat-box">
                    <div class="stat-label">Servings</div>
                    <div class="stat-val primary">{recipe.yield_info.servings:g} meals</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Portion (Cooked)</div>
                    <div class="stat-val">{portion_g:g} g</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Cost / Portion</div>
                    <div class="stat-val success">${serv_cost:.2f}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Safe Fridge</div>
                    <div class="stat-val">{safe_days} days</div>
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
{macro_boxes_html}
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
                        <strong style="color: #fff;">{raw_g:.1f} g</strong>
                    </div>
                    <div style="margin-top: 4px; font-size: 0.82rem; color: var(--text-muted); display: flex; justify-content: space-between;">
                        <span>Total Batch Cost:</span>
                        <strong style="color: var(--success);">${batch_cost:.2f} CAD</strong>
                    </div>
                </div>

                <div class="panel">
                    <h2 class="panel-title">🍳 Equipment</h2>
                    <div style="display: flex; flex-wrap: wrap; gap: 8px;">
                        {equipment_html}
                    </div>
                </div>

                <div class="panel">
                    <h2 class="panel-title">📦 Storage</h2>
                    <p class="storage-notes">
                        <strong>Fridge:</strong> Safe up to <strong>{safe_days} days</strong> in an airtight container.<br>
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



def render_all_recipe_cards(
    recipes_dir: Path | str = Path("recipes"),
    output_dir: Path | str = Path("recipe_cards"),
    library: Any | None = None,
    catalog: dict[str, Ingredient] | None = None,
    equipment: EquipmentRegistry | None = None,
    units: UnitsRegistry | None = None,
) -> list[Path]:
    """Render HTML recipe cards for all .cook files, mirroring the directory structure.

    Args:
        recipes_dir: Directory containing .cook files (e.g. `recipes/`).
        output_dir: Destination directory for rendered .html files (e.g. `recipe_cards/`).
        library: Optional preloaded MealPrepLibrary instance.
        catalog: Optional preloaded ingredients catalog.
        equipment: Optional preloaded equipment registry.
        units: Optional preloaded units registry.

    Returns:
        List of generated HTML file paths.
    """
    recipes_path = Path(recipes_dir)
    out_path = Path(output_dir)

    if library is None:
        if catalog is not None and equipment is not None and units is not None:
            from meal_prep.library import MealPrepLibrary
            from meal_prep.adapters.aisles import load_aisles
            aisles = load_aisles(Path("data/aisles.yaml"))
            from meal_prep.adapters.recipes import load_all_recipes
            recipes = load_all_recipes(recipes_path, catalog=catalog, equipment_reg=equipment, units_reg=units)
            library = MealPrepLibrary(units=units, equipment=equipment, aisles=aisles, catalog=catalog, recipes=recipes)
        else:
            from meal_prep.library import MealPrepLibrary
            library = MealPrepLibrary.load(recipes_dir=recipes_dir)

    rendered_files: list[Path] = []
    for prepared in library.prepare_all().values():
        cook_file = prepared.recipe.source_path
        if cook_file and recipes_path in cook_file.parents:
            rel_path = cook_file.relative_to(recipes_path)
        else:
            rel_path = Path(prepared.recipe.category.value) / f"{prepared.id}.cook"

        dest_html = (out_path / rel_path).with_suffix(".html")
        dest_html.parent.mkdir(parents=True, exist_ok=True)

        html_content = render_recipe_card_html(prepared)
        dest_html.write_text(html_content, encoding="utf-8")
        rendered_files.append(dest_html)

    return rendered_files


if __name__ == "__main__":
    generated = render_all_recipe_cards()
    print(f"Generated {len(generated)} recipe cards in recipe_cards/:")
    for p in generated:
        print(f"  - {p}")

