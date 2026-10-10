"""Regenerate committed JSON schemas from the DTOs.

Usage:
    python scripts/refresh_schemas.py

Writes schemas/ingredient.schema.json, schemas/log.schema.json,
schemas/meal.schema.json, and schemas/recipe.schema.json.
Run after any DTO change and commit the diff; tests/test_schemas.py
fails CI when the committed files drift from the live models.
"""

from __future__ import annotations

import json
from pathlib import Path

from meal_prep.dtos.ingredient import IngredientDTO
from meal_prep.dtos.log import LogWeekDTO
from meal_prep.dtos.meal import MealDTO
from meal_prep.dtos.recipe import RecipeDTO

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"

_DTOS = {
    "ingredient": IngredientDTO,
    "log": LogWeekDTO,
    "meal": MealDTO,
    "recipe": RecipeDTO,
}


def main() -> None:
    SCHEMA_DIR.mkdir(exist_ok=True)
    for name, dto in _DTOS.items():
        schema = json.dumps(dto.model_json_schema(), indent=2, sort_keys=True) + "\n"
        (SCHEMA_DIR / f"{name}.schema.json").write_text(schema, encoding="utf-8")
        print(f"wrote schemas/{name}.schema.json")


if __name__ == "__main__":
    main()
