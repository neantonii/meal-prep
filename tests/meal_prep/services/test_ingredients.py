"""Integration test: enrich the real ingredient catalog through the service.

This is a data-consistency smoke test, not a unit test. It loads every authored
ingredient and enriches it via ``prepare_catalog``. It asserts nothing about the
values — if any ingredient is malformed (unregistered unit, missing gram path,
colliding custom-unit synonym, invalid conversion graph, ...) the service raises
and the test fails.
"""

from __future__ import annotations

from pathlib import Path

from meal_prep.adapters.ingredients import load_all_ingredients
from meal_prep.adapters.units import load_units
from meal_prep.services.ingredients import prepare_catalog

_REPO_ROOT = Path(__file__).resolve().parents[3]


def test_all_ingredients_enrich_without_error():
    units = load_units(_REPO_ROOT / "data" / "units.yaml")
    dtos = load_all_ingredients(_REPO_ROOT / "data" / "ingredients")
    catalog = prepare_catalog(dtos, units)

    # No per-value assertions: merely that every authored ingredient enriched
    # without raising. This single guard only prevents a vacuous pass if the
    # catalog were accidentally empty.
    assert catalog
