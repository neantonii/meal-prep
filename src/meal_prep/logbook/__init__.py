"""Logbook report — render a resolved ``LogWeek`` as standalone HTML.

Same dark theme as the recipe cards and the week-plan report: a header with
week totals, one card per day with its mealtime slots, and a per-day macro
strip. Recipe titles link to their recipe cards
(``<cards_dir>/<category>/<slug>.html``) when a recipe lookup is provided;
otherwise they render as plain text.
"""

from __future__ import annotations

import html
from collections.abc import Mapping
from pathlib import Path

from meal_prep.enums import Mealtime
from meal_prep.models.log import LoggedSlot, LogWeek
from meal_prep.models.recipe import Recipe

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

        .log-header {
            background: linear-gradient(135deg, #1e293b 0%, #1e1b4b 100%);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 28px;
            margin-bottom: 24px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
        }

        .log-kicker {
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

        .log-title {
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

        .slot-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 12px;
        }

        .slot {
            background: var(--surface-card);
            border-radius: 8px;
            padding: 12px 14px;
        }

        .slot-label {
            font-size: 0.72rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--primary);
            margin-bottom: 4px;
        }

        .slot-recipe {
            font-size: 0.95rem;
            font-weight: 600;
            color: #ffffff;
        }

        .slot-recipe a {
            color: #ffffff;
            text-decoration: underline;
            text-decoration-color: var(--primary);
            text-underline-offset: 3px;
        }

        .slot-meta {
            font-size: 0.78rem;
            color: var(--text-muted);
            margin-top: 4px;
        }
"""


def _recipe_line(recipe: Recipe, cards_root: Path) -> str:
    """One recipe row; the title links to its card when the lookup hits."""
    href = (cards_root / recipe.category.value / f"{recipe.id}.html").as_posix()
    title = f'<a href="{html.escape(href)}">{html.escape(recipe.title)}</a>'
    meta = (
        f"${recipe.cost_per_portion:.2f} · "
        f"{recipe.per_serving_macros.calories_kcal:.0f} kcal · "
        f"{recipe.per_serving_macros.protein_g:.0f}g P"
    )
    return (
        f'<div class="slot-recipe">{title}</div>\n'
        f'    <div class="slot-meta">{html.escape(meta)}</div>'
    )


def _slot_html(
    slot: LoggedSlot,
    recipes: Mapping[str, Recipe],
    cards_root: Path,
) -> str:
    """One mealtime block with its recipes in logged order."""
    lines = []
    for recipe in slot.recipes:
        known = recipes.get(recipe.id)
        if known is None:
            lines.append(f'<div class="slot-recipe">{html.escape(recipe.title)}</div>')
        else:
            lines.append(_recipe_line(known, cards_root))
    body = "\n    ".join(lines)
    return (
        f'<div class="slot">\n'
        f'    <div class="slot-label">'
        f"{html.escape(slot.mealtime.display_name)}</div>\n"
        f"    {body}\n"
        f"</div>"
    )


def render_log_week(
    week: LogWeek,
    recipes: Mapping[str, Recipe] | None = None,
    cards_dir: str | Path = "recipe_cards",
) -> str:
    """Render ``week`` into a standalone HTML page."""
    by_id = dict(recipes) if recipes is not None else {}
    cards_root = Path(cards_dir)

    day_blocks = []
    for day in week.days:
        slots = [_slot_html(slot, by_id, cards_root) for slot in day.slots]
        macros = day.macros
        day_blocks.append(
            f'<section class="day-card">\n'
            f'    <h2 class="day-title"><span>{html.escape(day.date.isoformat())}'
            f" · {html.escape(day.date.strftime('%a'))}</span>"
            f"<span>${day.cost:.2f}</span></h2>\n"
            f'    <p class="day-macros">{macros.calories_kcal:.0f} kcal · '
            f"{macros.protein_g:.0f}g protein · {macros.fat_g:.0f}g fat · "
            f"{macros.carbs_g:.0f}g carbs</p>\n"
            f'    <div class="slot-grid">\n{"\n".join(slots)}\n    </div>\n'
            f"</section>"
        )
    days_html = "\n\n".join(day_blocks)
    total = week.total_macros
    day_count = len(week.days)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Eating Log — {html.escape(week.week)}</title>
    <style>{_CSS}
    </style>
</head>
<body>
    <div class="container">
        <header class="log-header">
            <span class="log-kicker">Eating Log · {html.escape(week.week)}</span>
            <h1 class="log-title">Logged Week</h1>

            <div class="stats-grid">
                <div class="stat-box">
                    <div class="stat-label">Total Cost</div>
                    <div class="stat-val success">${week.total_cost:.2f}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Avg / Day</div>
                    <div class="stat-val">${week.total_cost / day_count:.2f}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Week Calories</div>
                    <div class="stat-val primary">{total.calories_kcal:.0f} kcal</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Week Protein</div>
                    <div class="stat-val">{total.protein_g:.0f} g</div>
                </div>
            </div>
        </header>

        {days_html}
    </div>
</body>
</html>
"""


def render_log_week_page(
    week: LogWeek,
    output_path: str | Path,
    recipes: Mapping[str, Recipe] | None = None,
    cards_dir: str | Path = "recipe_cards",
) -> Path:
    """Write ``week`` to ``output_path`` as standalone HTML; return the path."""
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        render_log_week(week, recipes=recipes, cards_dir=cards_dir), encoding="utf-8"
    )
    return target


__all__ = ["Mealtime", "render_log_week", "render_log_week_page"]
