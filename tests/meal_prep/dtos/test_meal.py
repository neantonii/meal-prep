"""Tests for the meal DTO (``dtos/meal.py``).

Happy paths plus our custom validation only. Pydantic's implicit field
constraints (``min_length``, extra-key rejection) are not re-tested.

Our custom validation in this module:
- ``MealDTO.validate_id_format`` -> ``normalize_slug``
- ``MealDTO.validate_recipe_ids`` -> ``normalize_slug`` per entry
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from meal_prep.dtos.meal import MealDTO


def _meal(**overrides):
    data = {
        "id": "hearty-eggs-toast-coffee",
        "title": "Scrambled Eggs + Toast + Coffee",
        "recipes": ["scrambled-eggs", "buttered-toast", "coffee-with-milk"],
    }
    data.update(overrides)
    return data


def test_meal_valid():
    meal = MealDTO.model_validate(_meal())
    assert meal.id == "hearty-eggs-toast-coffee"
    assert meal.recipes == ["scrambled-eggs", "buttered-toast", "coffee-with-milk"]
    assert meal.source_path is None


def test_meal_ids_are_normalized():
    meal = MealDTO.model_validate(
        _meal(id="  Hearty-Eggs  ", recipes=["  Scrambled-Eggs  "])
    )
    assert meal.id == "hearty-eggs"
    assert meal.recipes == ["scrambled-eggs"]


def test_meal_allows_duplicate_recipe_ids():
    meal = MealDTO.model_validate(_meal(recipes=["oatmeal", "oatmeal"]))
    assert meal.recipes == ["oatmeal", "oatmeal"]


def test_meal_id_invalid_slug_is_rejected():
    with pytest.raises(ValidationError, match="kebab-case slug"):
        MealDTO.model_validate(_meal(id="hearty_eggs"))


def test_meal_recipe_id_invalid_slug_is_rejected():
    with pytest.raises(ValidationError, match="kebab-case slug"):
        MealDTO.model_validate(_meal(recipes=["scrambled eggs"]))


def test_meal_rejects_empty_recipes():
    with pytest.raises(ValidationError):
        MealDTO.model_validate(_meal(recipes=[]))
