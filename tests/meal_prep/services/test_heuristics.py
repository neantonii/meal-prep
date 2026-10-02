"""Tests for the warn-only heuristics (``services/heuristics.py``).

``check_ingredient`` takes an enriched ingredient and returns warning strings;
it never raises and never gates enrichment. Tests use real catalog entries
plus targeted mutations for each tripwire.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from meal_prep.adapters.aisles import load_aisles
from meal_prep.adapters.ingredients import load_all_ingredients
from meal_prep.adapters.units import load_units
from meal_prep.services.heuristics import check_ingredient
from meal_prep.services.ingredients import prepare_ingredient

_REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def catalog():
    units = load_units(_REPO_ROOT / "data" / "units.yaml")
    aisle_map = {a.id: a for a in load_aisles(_REPO_ROOT / "data" / "aisles.yaml")}
    dtos = load_all_ingredients(_REPO_ROOT / "data" / "ingredients")
    return {i: prepare_ingredient(d, units, aisle_map) for i, d in dtos.items()}


def test_clean_entries_produce_no_warnings(catalog):
    assert check_ingredient(catalog["unsalted-butter"]) == []
    assert check_ingredient(catalog["boneless-chicken-breast"]) == []


def test_atwater_flags_mislabeled_calories(catalog):
    bad = replace(
        catalog["unsalted-butter"],
        macros_per_100g=replace(
            catalog["unsalted-butter"].macros_per_100g, calories_kcal=100.0
        ),
    )
    assert any("atwater" in w for w in check_ingredient(bad))


def test_macro_sum_flags_impossible_totals(catalog):
    bad = replace(
        catalog["unsalted-butter"],
        macros_per_100g=replace(
            catalog["unsalted-butter"].macros_per_100g, protein_g=90.0
        ),
    )
    assert any("macro-sum" in w for w in check_ingredient(bad))


def test_price_flags_out_of_band(catalog):
    bad = replace(catalog["kosher-salt"], price_per_100g=50.0)
    assert any("price" in w for w in check_ingredient(bad))


def test_shelf_life_flags_out_of_band(catalog):
    bad = replace(catalog["boneless-chicken-breast"], shelf_life_days=120)
    assert any("shelf-life" in w for w in check_ingredient(bad))
