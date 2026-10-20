"""Render a week YAML (plan or diary) to a standalone HTML page.

Usage:
    python scripts/render_week.py plans/2026-W43.yaml
    python scripts/render_week.py diary/2026-W43.yaml -o weekly_plan/diary-2026-W43.html

Defaults: output goes to ``weekly_plan/<stem>.html``; recipe cards are
regenerated first so links never go stale.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from meal_prep.adapters.logs import load_log_file
from meal_prep.library import MealPrepLibrary
from meal_prep.logbook import render_log_week_page
from meal_prep.services.logs import prepare_log_week
from meal_prep.services.recipes import prepare_recipe

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a week YAML to HTML.")
    parser.add_argument("week_yaml", type=Path, help="e.g. plans/2026-W43.yaml")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="default: weekly_plan/<stem>.html",
    )
    args = parser.parse_args()

    sys.path.insert(0, str(ROOT))
    import renderer

    lib = MealPrepLibrary.load(ROOT / "data", ROOT / "recipes")
    prepared = {
        rid: prepare_recipe(r, lib.catalog, lib.equipment)
        for rid, r in lib.recipes.items()
    }
    renderer.render_all_recipe_cards(lib, ROOT / "recipe_cards")

    week = prepare_log_week(load_log_file(args.week_yaml), prepared)
    stem = args.week_yaml.stem
    default_name = stem if stem.startswith(("log-", "diary-")) else f"log-{stem}"
    target = args.output or (ROOT / "weekly_plan" / f"{default_name}.html")
    render_log_week_page(
        week, target, recipes=prepared, cards_dir=ROOT / "recipe_cards"
    )
    print(f"wrote {target} ({len(week.days)} days)")


if __name__ == "__main__":
    main()
