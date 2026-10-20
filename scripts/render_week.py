"""Render a week YAML (plan or diary) to a standalone HTML page.

Usage (run from the workspace root):
    python scripts/render_week.py plans/2026-W43.yaml
    python scripts/render_week.py diary/2026-W43.yaml -o weekly_plan/diary-2026-W43.html

All locations are explicit parameters (CWD-relative by default); nothing is
derived from the script's own path. Recipe cards are regenerated first so
links never go stale.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from meal_prep import renderer
from meal_prep.adapters.logs import load_log_file
from meal_prep.library import MealPrepLibrary
from meal_prep.logbook import render_log_week_page
from meal_prep.services.logs import prepare_log_week
from meal_prep.services.recipes import prepare_recipe


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a week YAML to HTML.")
    parser.add_argument("week_yaml", type=Path, help="e.g. plans/2026-W43.yaml")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--recipes-dir", type=Path, default=Path("recipes"))
    parser.add_argument("--cards-dir", type=Path, default=Path("recipe_cards"))
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="default: weekly_plan/log-<stem>.html",
    )
    args = parser.parse_args()

    lib = MealPrepLibrary.load(args.data_dir, args.recipes_dir)
    prepared = {
        rid: prepare_recipe(r, lib.catalog, lib.equipment)
        for rid, r in lib.recipes.items()
    }
    renderer.render_all_recipe_cards(lib, args.cards_dir)

    week = prepare_log_week(load_log_file(args.week_yaml), prepared)
    stem = args.week_yaml.stem
    default_name = stem if stem.startswith(("log-", "diary-")) else f"log-{stem}"
    target = args.output or (Path("weekly_plan") / f"{default_name}.html")
    render_log_week_page(week, target, recipes=prepared, cards_dir=args.cards_dir)
    print(f"wrote {target} ({len(week.days)} days)")


if __name__ == "__main__":
    main()
