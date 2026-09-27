"""Tests for the units taxonomy DTOs (``dtos/units.py``).

These models have no custom validation — they are pure shape declarations —
so only happy paths are covered. Pydantic's implicit type/required-field checks
are not re-tested here.
"""

from __future__ import annotations

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
