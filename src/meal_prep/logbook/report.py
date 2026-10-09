"""Logbook HTML report — render a resolved ``LogWeek`` as standalone HTML.

Weekly-menu table layout: one row per day, one column per mealtime, with
day totals and a week-totals footer. Same dark theme as the recipe cards
and the week-plan report.

Recipe titles link to their recipe cards
(``<cards_dir>/<category>/<slug>.html``) only when a recipe lookup *and* a
cards dir are provided; otherwise they render as plain text.
"""

from __future__ import annotations

import html
from collections.abc import Mapping
from pathlib import Path

from meal_prep.enums import Mealtime
from meal_prep.models.log import LoggedMeal, LogWeek
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
            max-width: 1100px;
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

        .table-wrap {
            overflow-x: auto;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 14px;
        }

        .log-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
        }

        .log-table th,
        .log-table td {
            padding: 10px 12px;
            border-bottom: 1px solid var(--border);
            border-right: 1px solid var(--border);
            text-align: left;
            vertical-align: top;
        }

        .log-table th:last-child,
        .log-table td:last-child {
            border-right: none;
        }

        .log-table thead th {
            background: var(--surface-card);
            font-size: 0.72rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--primary);
            white-space: nowrap;
        }

        .log-table tbody tr:nth-child(even) {
            background: rgba(255, 255, 255, 0.02);
        }

        .day-cell {
            white-space: nowrap;
            font-weight: 700;
        }

        .day-cell .date {
            display: block;
            font-weight: 400;
            font-size: 0.78rem;
            color: var(--text-muted);
        }

        .day-cell .day-total {
            display: block;
            font-weight: 400;
            font-size: 0.78rem;
            color: var(--text-muted);
            margin-top: 6px;
            white-space: normal;
            min-width: 150px;
        }

        .empty {
            color: var(--text-muted);
        }

        .meal-recipe {
            font-weight: 600;
            color: #ffffff;
        }

        .meal-recipe a {
            color: #ffffff;
            text-decoration: underline;
            text-decoration-color: var(--primary);
            text-underline-offset: 3px;
        }

        .meal-meta {
            font-size: 0.78rem;
            color: var(--text-muted);
            margin-bottom: 6px;
        }

        .meal-meta:last-child {
            margin-bottom: 0;
        }
"""


def _kcal(value: float) -> str:
    """Calories with thousands separator, e.g. 11,604 kcal."""
    return f"{value:,.0f} kcal"


def _recipe_cell(recipe: Recipe, cards_root: Path | None) -> str:
    """One recipe title plus its per-serving calories line."""
    if cards_root is None:
        title = html.escape(recipe.title)
    else:
        href = (cards_root / recipe.category.value / f"{recipe.id}.html").as_posix()
        title = f'<a href="{html.escape(href)}">{html.escape(recipe.title)}</a>'
    meta = _kcal(recipe.per_serving_macros.calories_kcal)
    return (
        f'<div class="meal-recipe">{title}</div>\n'
        f'<div class="meal-meta">{html.escape(meta)}</div>'
    )


def _meal_cell(meal: LoggedMeal | None, cards_root: Path | None) -> str:
    """One table cell: the mealtime's recipes in logged order, or a dash."""
    if meal is None:
        return '<td><span class="empty">—</span></td>'
    body = "\n".join(_recipe_cell(recipe, cards_root) for recipe in meal.recipes)
    return f"<td>{body}</td>"


def render_log_week(
    week: LogWeek,
    recipes: Mapping[str, Recipe] | None = None,
    cards_dir: str | Path | None = None,
) -> str:
    """Render ``week`` into a standalone HTML page.

    Titles link to their recipe cards only when both ``recipes`` and
    ``cards_dir`` are given; the report itself assumes nothing about where
    cards live.
    """
    cards_root = Path(cards_dir) if cards_dir is not None else None

    rows = []
    for day in week.days:
        cells = [_meal_cell(day.meal(mealtime), cards_root) for mealtime in Mealtime]
        macros = day.macros
        rows.append(
            f"<tr>\n"
            f'    <td class="day-cell">{html.escape(day.date.strftime("%a"))}'
            f'<span class="date">{html.escape(day.date.isoformat())}</span>'
            f'<span class="day-total">${day.cost:.2f} · '
            f"{_kcal(macros.calories_kcal)}<br><br>"
            f"{macros.protein_g:,.0f}g protein<br>"
            f"{macros.carbs_g:,.0f}g carbs<br>"
            f"{macros.fat_g:,.0f}g fat<br>"
            f"{macros.fiber_g:,.0f}g fiber</span></td>\n"
            f"    {'\n    '.join(cells)}\n"
            f"</tr>"
        )
    body_html = "\n".join(rows)
    total = week.total_macros
    headers = "".join(
        f"<th>{html.escape(mealtime.display_name)}</th>" for mealtime in Mealtime
    )

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
                    <div class="stat-label">Week Calories</div>
                    <div class="stat-val primary">{_kcal(total.calories_kcal)}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Week Protein</div>
                    <div class="stat-val">{total.protein_g:,.0f} g</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Week Carbs</div>
                    <div class="stat-val">{total.carbs_g:,.0f} g</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Week Fat</div>
                    <div class="stat-val">{total.fat_g:,.0f} g</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Week Fiber</div>
                    <div class="stat-val">{total.fiber_g:,.0f} g</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Total Cost</div>
                    <div class="stat-val success">${week.total_cost:,.2f}</div>
                </div>
            </div>
        </header>

        <div class="table-wrap">
        <table class="log-table">
            <thead>
                <tr><th>Day</th>{headers}</tr>
            </thead>
            <tbody>
{body_html}
            </tbody>
        </table>
        </div>
    </div>
</body>
</html>
"""


def render_log_week_page(
    week: LogWeek,
    output_path: str | Path,
    recipes: Mapping[str, Recipe] | None = None,
    cards_dir: str | Path | None = None,
) -> Path:
    """Write ``week`` to ``output_path`` as standalone HTML; return the path."""
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        render_log_week(week, recipes=recipes, cards_dir=cards_dir), encoding="utf-8"
    )
    return target


__all__ = ["render_log_week", "render_log_week_page"]
