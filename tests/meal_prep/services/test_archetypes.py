"""Archetypes resolved against the recipes (``data/archetypes.yaml``)."""

from __future__ import annotations

from pathlib import Path

import pytest

from meal_prep.dtos.archetypes import ArchetypesDTO
from meal_prep.enums import Mealtime
from meal_prep.library import load_library
from meal_prep.models.archetype import TAKEOUT
from meal_prep.models.library import Library
from meal_prep.services.archetypes import prepare_archetypes

_REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def library() -> Library:
    return load_library(_REPO_ROOT / "data", _REPO_ROOT / "recipes")


def _one(role: dict[str, object]) -> ArchetypesDTO:
    return ArchetypesDTO.model_validate({"snacks": [{"name": "test", "roles": [role]}]})


def test_the_authored_file_resolves_for_every_mealtime(library: Library):
    assert set(library.archetypes) == set(Mealtime)
    assert all(library.archetypes[m] for m in Mealtime)


def test_takeout_roles_take_takeout(library: Library):
    (eat_out,) = (a for a in library.archetypes[Mealtime.DINNER] if not a.plannable)
    assert eat_out.roles[0].accepts(TAKEOUT, None)


def test_an_unknown_recipe_is_refused(library: Library):
    dto = _one({"name": "x", "recipes": ["no-such-recipe"], "missing": 1, "extra": 1})
    with pytest.raises(ValueError, match="unknown recipe"):
        prepare_archetypes(dto, library.recipes)


def test_a_role_no_recipe_fits_is_refused():
    dto = _one({"name": "x", "categories": ["snacks"], "missing": 1, "extra": 1})
    with pytest.raises(ValueError, match="no recipe fits"):
        prepare_archetypes(dto, {})


def test_a_recipe_fitting_two_roles_is_refused(library: Library):
    dto = ArchetypesDTO.model_validate(
        {
            "snacks": [
                {
                    "name": "test",
                    "roles": [
                        {
                            "name": "a",
                            "categories": ["snacks"],
                            "missing": 1,
                            "extra": 1,
                        },
                        {
                            "name": "b",
                            "recipes": ["honeycrisp-apple"],
                            "missing": 1,
                            "extra": 1,
                        },
                    ],
                }
            ]
        }
    )
    with pytest.raises(ValueError, match="fits roles a, b"):
        prepare_archetypes(dto, library.recipes)


def test_a_role_needs_a_pool_and_a_sane_count():
    with pytest.raises(ValueError, match="empty pool"):
        _one({"name": "x", "missing": 1, "extra": 1})
    with pytest.raises(ValueError, match="fewest"):
        _one({"name": "x", "takeout": True, "count": [2, 1], "missing": 1, "extra": 1})
