"""Tests for the ingredient enrichment service (``services/ingredients.py``).

Focused on the aisle resolution added to ``prepare_ingredient``: the authored
aisle slug is resolved to its display name and walking order, and an unknown
aisle is rejected rather than carried through unresolved.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from meal_prep.adapters.aisles import load_aisles
from meal_prep.adapters.ingredients import load_all_ingredients
from meal_prep.adapters.units import load_units
from meal_prep.services.ingredients import prepare_ingredient

_REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def units():
    return load_units(_REPO_ROOT / "data" / "units.yaml")


@pytest.fixture(scope="module")
def aisles():
    return load_aisles(_REPO_ROOT / "data" / "aisles.yaml")


@pytest.fixture(scope="module")
def aisle_map(aisles):
    return {a.id: a for a in aisles}


@pytest.fixture(scope="module")
def butter_dto():
    return load_all_ingredients(_REPO_ROOT / "data" / "ingredients")["unsalted-butter"]


def test_prepare_ingredient_resolves_aisle(units, aisle_map, butter_dto):
    ingredient = prepare_ingredient(butter_dto, units, aisle_map)
    assert ingredient.aisle_name == "Dairy"
    assert ingredient.aisle_order == 5


def test_prepare_ingredient_rejects_unknown_aisle(units, aisle_map, butter_dto):
    partial = dict(aisle_map)
    del partial["dairy"]
    with pytest.raises(ValueError, match="unknown aisle 'dairy'"):
        prepare_ingredient(butter_dto, units, partial)
