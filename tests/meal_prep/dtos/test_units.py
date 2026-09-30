"""Tests for the units taxonomy DTOs (``dtos/units.py``).

These models have no custom validation — they are pure shape declarations —
so only happy paths are covered. Pydantic's implicit type/required-field checks
are not re-tested here.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from meal_prep.dtos.units import ConversionStep, DimensionGroup, UnitsFileSchema


def test_conversion_step_valid():
    step = ConversionStep.model_validate({"amount": 15, "unit": "ml"})
    assert step.amount == 15
    assert step.unit == "ml"


def test_dimension_group_valid():
    group = DimensionGroup.model_validate(
        {
            "base": "g",
            "allowed": {"g": ["gram", "grams"]},
            "conversions": {"kg": {"amount": 1000, "unit": "g"}},
        }
    )
    assert group.base == "g"
    assert group.allowed == {"g": ["gram", "grams"]}
    assert group.conversions["kg"].unit == "g"


def test_dimension_group_defaults_are_empty():
    group = DimensionGroup.model_validate({"base": "g"})
    assert group.allowed == {}
    assert group.conversions == {}


def test_units_file_schema_valid():
    schema = UnitsFileSchema.model_validate(
        {
            "mass": {"base": "g"},
            "volume": {"base": "ml"},
            "package": {"base": "package"},
        }
    )
    assert schema.mass.base == "g"
    assert schema.volume.base == "ml"
    assert schema.package.base == "package"


def test_units_file_schema_count_defaults_to_reserved_node():
    schema = UnitsFileSchema.model_validate(
        {
            "mass": {"base": "g"},
            "volume": {"base": "ml"},
            "package": {"base": "package"},
        }
    )
    assert schema.count.base == "count"


# ---------------------------------------------------------------------------
# strict boundaries — extra keys rejected, tokens normalized
# ---------------------------------------------------------------------------


def test_conversion_step_rejects_extra_keys():
    with pytest.raises(ValidationError, match="Extra"):
        ConversionStep.model_validate({"amount": 15, "unit": "ml", "units": "ml"})


def test_conversion_step_rejects_non_positive_amount():
    with pytest.raises(ValidationError):
        ConversionStep.model_validate({"amount": 0, "unit": "ml"})


def test_dimension_group_normalizes_allowed_tokens():
    group = DimensionGroup.model_validate(
        {"base": "G", "allowed": {"KG": ["Kilogram"]}}
    )
    assert group.base == "g"
    assert group.allowed == {"kg": ["kilogram"]}


def test_dimension_group_rejects_duplicate_alias():
    with pytest.raises(ValidationError, match="Duplicate alias"):
        DimensionGroup.model_validate({"base": "g", "allowed": {"g": ["gram", "gram"]}})
