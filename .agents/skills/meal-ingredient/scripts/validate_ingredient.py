"""Validate one ingredient entry: enrich it and report errors and warnings.

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
from meal_prep.dtos.ingredient import IngredientDTO  # noqa: E402
from meal_prep.services.heuristics import check_ingredient  # noqa: E402
from meal_prep.services.ingredients import prepare_ingredient  # noqa: E402


def _enrich(dto: IngredientDTO) -> dict:
    units = load_units(REPO_ROOT / "data" / "units.yaml")
    aisles = {a.id: a for a in load_aisles(REPO_ROOT / "data" / "aisles.yaml")}
    ingredient = prepare_ingredient(dto, units, aisles)
    macros = ingredient.macros_per_100g
    return {
        "ok": True,
        "errors": [],
        "warnings": check_ingredient(ingredient),
        "derived": {
            "package_weight_g": round(ingredient.package_weight_g, 1),
            "price_per_100g": round(ingredient.price_per_100g, 2),
            "calories_kcal": round(macros.calories_kcal),
            "protein_g": round(macros.protein_g, 1),
            "fat_g": round(macros.fat_g, 1),
            "carbs_g": round(macros.carbs_g, 1),
            "fiber_g": round(macros.fiber_g, 1),
        },
    }


def _validate_file(path: Path, entry_id: str) -> int:
    try:
        dto = next(d for d in load_ingredients_file(path) if d.id == entry_id)
        result = _enrich(dto)
    except (ValueError, FileNotFoundError, StopIteration) as e:
        print(f"ERROR: {e}")
        return 1

    for warning in result["warnings"]:
        print(f"WARN {warning}")

    derived = result["derived"]
    print(
        f"OK {entry_id}: package {derived['package_weight_g']:.1f}g, ${derived['price_per_100g']:.2f}/100g"
    )
    print(
        f"   per-100g: {derived['calories_kcal']:.0f} kcal, "
        f"P {derived['protein_g']:.1f}g, F {derived['fat_g']:.1f}g, "
        f"C {derived['carbs_g']:.1f}g, fiber {derived['fiber_g']:.1f}g"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate one ingredient entry.")
    parser.add_argument("file", type=Path, help="Aisle YAML file")
    parser.add_argument("--id", required=True, help="Ingredient slug")
    args = parser.parse_args()

    return _validate_file(args.file, args.id)


if __name__ == "__main__":
    raise SystemExit(main())
