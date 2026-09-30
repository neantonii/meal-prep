"""Week-plan HTML report.

Renders a solved ``WeekPlan`` into a standalone HTML page in the same dark
theme as the recipe cards: a header with week totals, one card per day with
its three meals, and a per-day macro strip. Meal titles link to the matching
recipe card (``<cards_dir>/<category>/<slug>.html``) when a recipe lookup is
provided; otherwise they render as plain text.
"""

from __future__ import annotations

import html
from collections.abc import Mapping
from pathlib import Path

from meal_prep.models.recipe import Recipe
from meal_prep.planner.plan import WeekPlan

MEAL_SLOT_NAMES = ("Breakfast", "Lunch", "Dinner")

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
            --success: #10b981;
            --warning: #f59e0b;
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

        .plan-header {
            background: linear-gradient(135deg, #1e293b 0%, #1e1b4b 100%);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 28px;
            margin-bottom: 24px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
        }

        .plan-kicker {
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

        .plan-title {
            font-size: 2rem;
            font-weight: 800;
            margin-bottom: 16px;
            color: #ffffff;
            letter-spacing: -0.02em;
        }

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

        .day-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 20px;
            margin-bottom: 20px;
        }

        .day-title {
            font-size: 1.1rem;
            font-weight: 700;
            margin-bottom: 4px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .day-macros {
            font-size: 0.82rem;
            color: var(--text-muted);
            margin-bottom: 14px;
        }

        .meal-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 12px;
        }

        .meal {
            background: var(--surface-card);
            border-radius: 8px;
            padding: 12px 14px;
        }

        .meal-label {
            font-size: 0.72rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--primary);
            margin-bottom: 4px;
        }

        .meal-name {
            font-size: 0.95rem;
            font-weight: 600;
            color: #ffffff;
        }

        .meal-name a {
            color: #ffffff;
            text-decoration: underline;
            text-decoration-color: var(--primary);
            text-underline-offset: 3px;
        }

        .meal-meta {
            font-size: 0.78rem;
            color: var(--text-muted);
            margin-top: 4px;
        }
"""


def _meal_html(
    meal_label: str,
    recipe_id: str,
    title: str,
    meta: str,
    card_href: str | None,
) -> str:
    """One meal block; the title links to its recipe card when known."""
    if card_href is not None:
        meal = f'<a href="{html.escape(card_href)}">{html.escape(title)}</a>'
    else:
        meal = html.escape(title)
    return (
        f'<div class="meal">\n'
        f'    <div class="meal-label">{html.escape(meal_label)}</div>\n'
        f'    <div class="meal-name">{meal}</div>\n'
        f'    <div class="meal-meta">{html.escape(meta)}</div>\n'
        f"</div>"
    )


def render_week_plan(
    plan: WeekPlan,
    recipes: Mapping[str, Recipe] | None = None,
    cards_dir: str | Path = "recipe_cards",
) -> str:
    """Render ``plan`` into a standalone HTML page."""
    by_id = dict(recipes) if recipes is not None else {}
    cards_root = Path(cards_dir)

    day_blocks = []
    for day in plan.days:
        meals = []
        day_meals = (day.breakfast, day.lunch, day.dinner)
        for label, meal in zip(MEAL_SLOT_NAMES, day_meals, strict=True):
            recipe = by_id.get(meal.recipe_id)
            href: str | None = None
            if recipe is not None:
                href = (
                    cards_root / recipe.category.value / f"{recipe.id}.html"
                ).as_posix()
            meals.append(
                _meal_html(
                    label,
                    meal.recipe_id,
                    meal.title,
                    f"${meal.cost:.2f} · "
                    f"{meal.macros.calories_kcal:.0f} kcal · "
                    f"{meal.macros.protein_g:.0f}g P",
                    href,
                )
            )
        macros = day.macros
        day_blocks.append(
            f'<section class="day-card">\n'
            f'    <h2 class="day-title"><span>{html.escape(day.day)}</span>'
            f"<span>${day.cost:.2f}</span></h2>\n"
            f'    <p class="day-macros">{macros.calories_kcal:.0f} kcal · '
            f"{macros.protein_g:.0f}g protein · {macros.fat_g:.0f}g fat · "
            f"{macros.carbs_g:.0f}g carbs</p>\n"
            f'    <div class="meal-grid">\n{"\n".join(meals)}\n    </div>\n'
            f"</section>"
        )
    days_html = "\n\n".join(day_blocks)
    week = plan.week_macros

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Weekly Meal Plan — 7 Days</title>
    <style>{_CSS}
    </style>
</head>
<body>
    <div class="container">
        <header class="plan-header">
            <span class="plan-kicker">Weekly Meal Plan · 7 days x 3 meals</span>
            <h1 class="plan-title">Cheapest Week</h1>

            <div class="stats-grid">
                <div class="stat-box">
                    <div class="stat-label">Total Cost</div>
                    <div class="stat-val success">${plan.total_cost:.2f}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Avg / Day</div>
                    <div class="stat-val">${plan.total_cost / 7:.2f}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Week Calories</div>
                    <div class="stat-val primary">{week.calories_kcal:.0f} kcal</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Week Protein</div>
                    <div class="stat-val">{week.protein_g:.0f} g</div>
                </div>
            </div>
        </header>

        {days_html}
    </div>
</body>
</html>
"""


def render_week_plan_page(
    plan: WeekPlan,
    output_path: str | Path,
    recipes: Mapping[str, Recipe] | None = None,
    cards_dir: str | Path = "recipe_cards",
) -> Path:
    """Write ``plan`` to ``output_path`` as standalone HTML; return the path."""
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        render_week_plan(plan, recipes=recipes, cards_dir=cards_dir), encoding="utf-8"
    )
    return target
