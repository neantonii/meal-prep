"""Tests for the prep session DTOs (``dtos/session.py``).

Our custom validation in this module:
- ``PrepSessionDTO.validate_unique_recipes`` -> one item per recipe
- recipe and ingredient ids are normalized slugs
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from meal_prep.dtos.session import PrepSessionDTO


def _item(recipe: str = "air-fried-chicken-breast", **overrides) -> dict:
    data = {
        "recipe": recipe,
        "title": "Chicken",
        "batches": 2,
        "servings": 4,
        "cost": 3.0,
        "calories_kcal": 250.0,
        "protein_g": 40.0,
        "fat_g": 5.0,
        "carbs_g": 0.0,
        "fiber_g": 0.0,
        "saturated_fat_g": 1.0,
        "sugars_g": 0.0,
        "sodium_mg": 90.0,
        "potassium_mg": 400.0,
        "ingredients": [
            {
                "ingredient": "chicken-breast",
                "name": "Chicken",
                "grams": 600,
                "cost": 12,
            }
        ],
    }
    data.update(overrides)
    return data


def _session(*items: dict) -> dict:
    return {"id": str(uuid.uuid4()), "date": "2026-11-01", "items": list(items)}


def test_session_valid():
    session = PrepSessionDTO.model_validate(_session(_item()))
    [item] = session.items
    assert (item.batches, item.servings) == (2, 4)
    assert item.ingredients[0].ingredient == "chicken-breast"


def test_session_rejects_a_recipe_listed_twice():
    with pytest.raises(ValidationError, match="listed twice"):
        PrepSessionDTO.model_validate(_session(_item(), _item()))


@pytest.mark.parametrize(
    "bad", [{"batches": 0}, {"batches": 1.5}, {"servings": 2.5}, {"extra": 1}]
)
def test_item_rejects_bad_amounts_and_unknown_fields(bad: dict):
    with pytest.raises(ValidationError):
        PrepSessionDTO.model_validate(_session(_item(**bad)))


def test_session_needs_an_item():
    with pytest.raises(ValidationError):
        PrepSessionDTO.model_validate(_session())


def test_ids_are_slugs():
    with pytest.raises(ValidationError):
        PrepSessionDTO.model_validate(_session(_item(recipe="Not A Slug")))


def test_deprecated_ad_hoc_field_still_loads():
    """Session files written before #145 carry ``ad_hoc``; they must load."""
    session = PrepSessionDTO.model_validate(_session(_item(ad_hoc=True)))
    assert session.items[0].recipe == "air-fried-chicken-breast"
