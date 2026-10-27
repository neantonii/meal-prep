"""Render a diary week to a standalone HTML page.

Usage (run from the workspace root):
    python scripts/render_week.py diary/2026-W43.yaml
    (writes weekly_plan/diary-2026-W43.html; -o to choose another path)

All locations are explicit parameters (CWD-relative by default); nothing is
derived from the script's own path. Recipe cards are regenerated first so
links never go stale.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from meal_prep import renderer
from meal_prep.adapters.logs import load_diary_file
from meal_prep.ingredient_cards import render_all_ingredient_cards
from meal_prep.library import load_library
from meal_prep.logbook import render_log_week_page
from meal_prep.services.logs import prepare_diary_week


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a diary week to HTML.")
    parser.add_argument("week_yaml", type=Path, help="e.g. diary/2026-W43.yaml")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--recipes-dir", type=Path, default=Path("recipes"))
    parser.add_argument("--cards-dir", type=Path, default=Path("recipe_cards"))
    parser.add_argument(
        "--ingredient-cards-dir", type=Path, default=Path("ingredient_cards")
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="default: weekly_plan/diary-<stem>.html",
    )
    args = parser.parse_args()

    library = load_library(args.data_dir, args.recipes_dir)
    render_all_ingredient_cards(library.ingredients.values(), args.ingredient_cards_dir)
    renderer.render_all_recipe_cards(
        library.recipes.values(),
        args.cards_dir,
        ingredient_cards_dir=args.ingredient_cards_dir,
    )

    week = prepare_diary_week(load_diary_file(args.week_yaml))
    stem = args.week_yaml.stem
    default_name = stem if stem.startswith("diary-") else f"diary-{stem}"
    target = args.output or (Path("weekly_plan") / f"{default_name}.html")
    render_log_week_page(
        week, target, recipes=library.recipes, cards_dir=args.cards_dir
    )
    print(f"wrote {target} ({len(week.days)} days)")


if __name__ == "__main__":
    main()
