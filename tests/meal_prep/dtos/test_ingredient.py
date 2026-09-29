"""Tests for the ingredient DTOs (``dtos/ingredient.py``).

Happy paths plus our custom validation only. Pydantic's implicit field
constraints (``gt``, ``min_length``, enum/type coercion) are not re-tested here.

Our custom validation in this module:
- ``Ingredient.validate_id`` -> ``normalize_slug``
- ``Ingredient.validate_name`` -> first character must be a capital letter
- ``Ingredient.validate_step_name`` -> first character must be a lowercase letter
- ``MacrosInfo.clean_unit`` / ``UnitConversion.clean_units`` -> ``clean_token``
- ``UnitConversion.validate_different_units`` -> reject self-conversion
- ``Ingredient.validate_custom_units`` -> slug keys, cleaned aliases, dedup
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from meal_prep.dtos.ingredient import (
    Ingredient,
    MacrosInfo,
    ReferenceInfo,
    UnitConversion,
)


# ---------------------------------------------------------------------------
# ReferenceInfo — no custom validation (happy path only)
# ---------------------------------------------------------------------------


def test_reference_info_valid():
    ref = ReferenceInfo.model_validate({"brand": "Compliments", "product": "Chicken 1kg", "price": 14.99})
    assert ref.brand == "Compliments"
    assert ref.product == "Chicken 1kg"
    assert ref.price == 14.99


# ---------------------------------------------------------------------------
# MacrosInfo — clean_unit
# ---------------------------------------------------------------------------


def _macros(**overrides):
    data = {
        "unit": "g",
        "amount": 100,
        "calories_kcal": 100,
        "protein_g": 10,
        "fat_g": 5,
        "carbs_g": 20,
        "fiber_g": 0,
    }
    data.update(overrides)
    return data


def test_macros_valid_minimal():
    m = MacrosInfo.model_validate(_macros())
    assert m.unit == "g"
    assert m.amount == 100
    assert m.saturated_fat_g is None
    assert m.sodium_mg is None


def test_macros_valid_with_optional_nutrients():
    m = MacrosInfo.model_validate(
        _macros(saturated_fat_g=1.0, sugars_g=2.0, sodium_mg=10.0, potassium_mg=20.0)
    )
    assert m.saturated_fat_g == 1.0
    assert m.sodium_mg == 10.0


def test_macros_unit_is_cleaned():
    assert MacrosInfo.model_validate(_macros(unit="  G  ")).unit == "g"


def test_macros_unit_whitespace_only_is_rejected():
    with pytest.raises(ValidationError, match="cannot be empty"):
        MacrosInfo.model_validate(_macros(unit="   "))


# ---------------------------------------------------------------------------
# UnitConversion — clean_units + validate_different_units
# ---------------------------------------------------------------------------


def test_unit_conversion_valid():
    uc = UnitConversion.model_validate({"from": "piece", "to": "g", "factor": 237.5})
    assert uc.from_unit == "piece"
    assert uc.to_unit == "g"
    assert uc.factor == 237.5


def test_unit_conversion_units_are_cleaned():
    uc = UnitConversion.model_validate({"from": " Piece ", "to": " G ", "factor": 237.5})
    assert uc.from_unit == "piece"
    assert uc.to_unit == "g"


def test_unit_conversion_whitespace_only_unit_is_rejected():
    with pytest.raises(ValidationError, match="cannot be empty"):
        UnitConversion.model_validate({"from": "  ", "to": "g", "factor": 1.0})


def test_unit_conversion_same_unit_is_rejected():
    with pytest.raises(ValidationError, match="to itself is redundant"):
        UnitConversion.model_validate({"from": "g", "to": "g", "factor": 1.0})


def test_unit_conversion_same_unit_different_case_is_rejected():
    # "g" vs "G" normalize to the same token, so it is still self-referential.
    with pytest.raises(ValidationError, match="to itself is redundant"):
        UnitConversion.model_validate({"from": "g", "to": "G", "factor": 1.0})


# ---------------------------------------------------------------------------
# Ingredient — validate_id (normalize_slug)
# ---------------------------------------------------------------------------


def _ingredient(**overrides):
    data = {
        "id": "boneless-chicken-breast",
        "name": "Boneless Chicken Breast",
        "aisle": "meat",
        "storage": "refrigerated",
        "shelf_life_days": 3,
        "reference": {"brand": "Compliments", "product": "Chicken Breast 1kg", "price": 14.99},
        "macros": {
            "unit": "g",
            "amount": 100,
            "calories_kcal": 165,
            "protein_g": 31,
            "fat_g": 3.6,
            "carbs_g": 0,
            "fiber_g": 0,
        },
        "conversions": [{"from": "package", "to": "g", "factor": 1000}],
    }
    data.update(overrides)
    return data


def test_ingredient_valid():
    ing = Ingredient.model_validate(_ingredient())
    assert ing.id == "boneless-chicken-breast"
    assert ing.storage.value == "refrigerated"
    assert ing.macros.amount == 100
    assert ing.conversions[0].from_unit == "package"


def test_ingredient_id_is_normalized():
    assert Ingredient.model_validate(_ingredient(id="  Boneless-Chicken-Breast  ")).id == (
        "boneless-chicken-breast"
    )


def test_ingredient_id_invalid_slug_is_rejected():
    with pytest.raises(ValidationError, match="kebab-case slug"):
        Ingredient.model_validate(_ingredient(id="boneless_chicken"))


# ---------------------------------------------------------------------------
# Ingredient — name / step_name casing
# ---------------------------------------------------------------------------


def test_name_must_start_with_capital_letter():
    assert Ingredient.model_validate(_ingredient(name="Boneless Chicken Breast")).name == (
        "Boneless Chicken Breast"
    )


def test_name_starting_lowercase_is_rejected():
    with pytest.raises(ValidationError, match="must start with a capital letter"):
        Ingredient.model_validate(_ingredient(name="boneless chicken breast"))


def test_name_starting_with_digit_is_rejected():
    with pytest.raises(ValidationError, match="must start with a capital letter"):
        Ingredient.model_validate(_ingredient(name="100% Pure Avocado Oil"))


def test_name_empty_is_rejected():
    with pytest.raises(ValidationError, match="must start with a capital letter"):
        Ingredient.model_validate(_ingredient(name=""))


def test_step_name_must_start_with_lowercase_letter():
    assert Ingredient.model_validate(_ingredient(step_name="chicken breast")).step_name == (
        "chicken breast"
    )


def test_step_name_starting_uppercase_is_rejected():
    with pytest.raises(ValidationError, match="must start with a lowercase letter"):
        Ingredient.model_validate(_ingredient(step_name="Chicken breast"))


def test_step_name_none_is_allowed():
    assert Ingredient.model_validate(_ingredient(step_name=None)).step_name is None


def test_step_name_empty_is_rejected():
    with pytest.raises(ValidationError, match="must start with a lowercase letter"):
        Ingredient.model_validate(_ingredient(step_name=""))


# ---------------------------------------------------------------------------
# Ingredient — validate_custom_units
# ---------------------------------------------------------------------------


def test_custom_units_normalizes_keys_and_aliases():
    ing = Ingredient.model_validate(_ingredient(custom_units={"Scoop": ["Scoop", "Scoops"]}))
    assert ing.custom_units["scoop"] == ["scoop", "scoops"]


def test_custom_units_does_not_insert_canonical_when_absent():
    # Aliases are stored exactly as authored; the canonical key is NOT
    # auto-inserted (mirrors the standard `allowed` map).
    ing = Ingredient.model_validate(_ingredient(custom_units={"scoop": ["scoops"]}))
    assert ing.custom_units["scoop"] == ["scoops"]


def test_custom_units_rejects_duplicate_alias():
    with pytest.raises(ValidationError, match="Duplicate alias"):
        Ingredient.model_validate(_ingredient(custom_units={"scoop": ["scoops", "scoops"]}))


def test_custom_units_rejects_invalid_key():
    with pytest.raises(ValidationError, match="kebab-case slug"):
        Ingredient.model_validate(_ingredient(custom_units={"scoop_size": ["s"]}))
