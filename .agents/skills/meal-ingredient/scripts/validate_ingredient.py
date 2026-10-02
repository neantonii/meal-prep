"""Validate one ingredient entry: enrich it and print heuristic warnings.

Usage:
    python validate_ingredient.py data/ingredients/<aisle>.yaml --id <slug>

Exit 0 when the entry enriches (warnings allowed); exit 1 on any error.
Run from the repo root so data/ and src/ resolve.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / "src"))

from meal_prep.adapters.aisles import load_aisles  # noqa: E402
from meal_prep.adapters.ingredients import load_ingredients_file  # noqa: E402
from meal_prep.adapters.units import load_units  # noqa: E402
from meal_prep.services.heuristics import check_ingredient  # noqa: E402
from meal_prep.services.ingredients import prepare_ingredient  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate one ingredient entry.")
    parser.add_argument("file", type=Path, help="Aisle YAML file")
    parser.add_argument("--id", required=True, help="Ingredient slug")
    args = parser.parse_args()

    try:
        units = load_units(REPO_ROOT / "data" / "units.yaml")
        aisles = {a.id: a for a in load_aisles(REPO_ROOT / "data" / "aisles.yaml")}
        dto = next(d for d in load_ingredients_file(args.file) if d.id == args.id)
        ingredient = prepare_ingredient(dto, units, aisles)
    except (ValueError, FileNotFoundError, StopIteration) as e:
        print(f"ERROR: {e}")
        return 1

    for warning in check_ingredient(ingredient):
        print(f"WARN {warning}")

    macros = ingredient.macros_per_100g
    print(
        f"OK {ingredient.id}: package {ingredient.package_weight_g:.1f}g, "
        f"${ingredient.price_per_100g:.2f}/100g"
    )
    print(
        f"   per-100g: {macros.calories_kcal:.0f} kcal, "
        f"P {macros.protein_g:.1f}g, F {macros.fat_g:.1f}g, "
        f"C {macros.carbs_g:.1f}g, fiber {macros.fiber_g:.1f}g"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
