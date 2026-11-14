"""Validate the library and regenerate every recipe and ingredient card.

Usage (run from the workspace root):
    python scripts/render_cards.py
    python scripts/render_cards.py chicken-cheese-soup-with-croutons
    (also prints each named recipe's per-portion numbers for the read-back)

All locations are explicit parameters (CWD-relative by default); nothing is
derived from the script's own path. Loading the library is the validation:
an unknown ingredient, unregistered unit or unknown cookware raises before
anything is written. Card directories are created if missing, and stale
cards are removed, so a renamed or deleted recipe leaves nothing behind. A
named recipe's card is also checked for timer residue (a stray ``%`` from a
malformed ``~timer``).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from meal_prep import renderer
from meal_prep.ingredient_cards import render_all_ingredient_cards
from meal_prep.library import load_library

# A Cooklang amount that survived into the card's text, e.g. "10%min".
_RESIDUE = re.compile(r">[^<]*\d%[a-z]+[^<]*<")


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate recipe cards.")
    parser.add_argument(
        "recipes", nargs="*", help="recipe ids to read back after rendering"
    )
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--recipes-dir", type=Path, default=Path("recipes"))
    parser.add_argument("--cards-dir", type=Path, default=Path("recipe_cards"))
    parser.add_argument(
        "--ingredient-cards-dir", type=Path, default=Path("ingredient_cards")
    )
    args = parser.parse_args()

    library = load_library(args.data_dir, args.recipes_dir)
    args.cards_dir.mkdir(parents=True, exist_ok=True)
    args.ingredient_cards_dir.mkdir(parents=True, exist_ok=True)
    render_all_ingredient_cards(library.ingredients.values(), args.ingredient_cards_dir)
    renderer.render_all_recipe_cards(
        library.recipes.values(),
        args.cards_dir,
        ingredient_cards_dir=args.ingredient_cards_dir,
    )
    print(
        f"wrote {len(library.recipes)} recipe cards to {args.cards_dir} and "
        f"{len(library.ingredients)} ingredient cards to {args.ingredient_cards_dir}"
    )

    failed = False
    for recipe_id in args.recipes:
        recipe = library.recipes.get(recipe_id)
        if recipe is None:
            print(f"{recipe_id}: no such recipe", file=sys.stderr)
            failed = True
            continue
        m = recipe.per_serving_macros
        card = args.cards_dir / recipe.category.value / f"{recipe.id}.html"
        print(
            f"{recipe.id}: {recipe.servings:g} servings, "
            f"{recipe.portion_cooked_g:.0f} g per portion, "
            f"${recipe.cost_per_portion:.2f} per portion\n"
            f"  per portion: {m.calories_kcal:.0f} kcal, {m.protein_g:.0f} g protein, "
            f"{m.carbs_g:.0f} g carbs, {m.fat_g:.0f} g fat, {m.fiber_g:.0f} g fiber, "
            f"{m.sodium_mg:.0f} mg sodium\n"
            f"  card: {card}"
        )
        residue = _RESIDUE.findall(card.read_text(encoding="utf-8"))
        if residue:
            print(f"  timer residue in card: {residue}", file=sys.stderr)
            failed = True
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
