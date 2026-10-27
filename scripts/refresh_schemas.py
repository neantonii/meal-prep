"""Regenerate committed JSON schemas from the DTOs.

Usage (run from the workspace root):
    python scripts/refresh_schemas.py
    python scripts/refresh_schemas.py --schemas-dir schemas

All locations are explicit parameters (CWD-relative by default); nothing is
derived from the script's own path.
Writes schemas/diary.schema.json, schemas/ingredient.schema.json,
schemas/meal.schema.json and schemas/recipe.schema.json.
Run after any DTO change and commit the diff; tests/test_schemas.py
fails CI when the committed files drift from the live models.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from meal_prep.dtos.ingredient import IngredientDTO
from meal_prep.dtos.log import DiaryWeekDTO
from meal_prep.dtos.meal import MealDTO
from meal_prep.dtos.recipe import RecipeDTO

_DTOS = {
    "diary": DiaryWeekDTO,
    "ingredient": IngredientDTO,
    "meal": MealDTO,
    "recipe": RecipeDTO,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate JSON schemas from DTOs.")
    parser.add_argument("--schemas-dir", type=Path, default=Path("schemas"))
    args = parser.parse_args()

    schema_dir: Path = args.schemas_dir
    schema_dir.mkdir(exist_ok=True)
    for name, dto in _DTOS.items():
        schema = json.dumps(dto.model_json_schema(), indent=2, sort_keys=True) + "\n"
        (schema_dir / f"{name}.schema.json").write_text(schema, encoding="utf-8")
        print(f"wrote {schema_dir / f'{name}.schema.json'}")


if __name__ == "__main__":
    main()
