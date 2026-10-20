"""Tests for the ingredient enrichment service (``services/ingredients.py``).

The authored ``aisle`` is a closed ``Aisle`` enum validated at DTO parse time,
so the service carries it through untouched — there is no aisle lookup and no
unknown-aisle error at this layer.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from meal_prep.adapters.ingredients import load_all_ingredients
from meal_prep.adapters.units import load_units
from meal_prep.dtos.ingredient import IngredientDTO
from meal_prep.enums import Aisle
from meal_prep.services.ingredients import prepare_ingredient

_REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def units():
    return load_units(_REPO_ROOT / "data" / "units.yaml")


@pytest.fixture(scope="module")
def butter_dto():
    return load_all_ingredients(_REPO_ROOT / "data" / "ingredients")["unsalted-butter"]


def test_prepare_ingredient_carries_aisle_enum(units, butter_dto):
    ingredient = prepare_ingredient(butter_dto, units)
    assert ingredient.aisle is Aisle.DAIRY


def test_ingredient_dto_rejects_unknown_aisle(butter_dto):
    data = butter_dto.model_dump()
    data["aisle"] = "bakery"
    with pytest.raises(ValidationError, match="bakery"):
        IngredientDTO.model_validate(data)
