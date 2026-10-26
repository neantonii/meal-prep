"""Tests for the log DTOs (``dtos/log.py``).

Happy paths plus our custom validation only. Pydantic's implicit field
constraints (``pattern``, ``min_length``, enum coercion) are not re-tested.

Our custom validation in this module:
- ``LogDayDTO.validate_recipe_ids`` -> normalizes slugs per mealtime
- ``LogDayDTO.validate_at_least_one_meal`` -> rejects empty days
- ``LogWeekDTO.validate_day_order`` -> strictly increasing dates
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from meal_prep.dtos.log import LogDayDTO, LogWeekDTO


def _day(day: str = "2026-10-13", **meals):
    data: dict = {"date": day}
    data.update(meals or {"breakfast": ["oatmeal"]})
    return data


def _week(**overrides):
    data = {"week": "2026-W42", "days": [_day()]}
    data.update(overrides)
    return data


def test_log_day_valid():
    day = LogDayDTO.model_validate(_day())
    assert day.breakfast == ["oatmeal"]
    assert day.lunch is None


def test_log_day_recipe_ids_are_normalized():
    day = LogDayDTO.model_validate(_day(breakfast=["  Oatmeal  "]))
    assert day.breakfast == ["oatmeal"]


def test_log_day_rejects_empty_meal_list():
    with pytest.raises(ValidationError):
        LogDayDTO.model_validate(_day(breakfast=[]))


def test_log_day_rejects_unknown_field():
    with pytest.raises(ValidationError):
        LogDayDTO.model_validate(_day(brunch=["oatmeal"]))


def test_log_day_rejects_day_without_meals():
    with pytest.raises(ValidationError, match="at least one mealtime"):
        LogDayDTO.model_validate({"date": "2026-10-13"})


def test_log_week_valid():
    week = LogWeekDTO.model_validate(_week())
    assert week.week == "2026-W42"
    assert len(week.days) == 1


def test_log_week_rejects_bad_week_label():
    with pytest.raises(ValidationError):
        LogWeekDTO.model_validate(_week(week="october"))


def test_log_week_rejects_unordered_days():
    with pytest.raises(ValidationError, match="increasing date order"):
        LogWeekDTO.model_validate(_week(days=[_day("2026-10-14"), _day("2026-10-13")]))


def test_log_week_rejects_duplicate_dates():
    with pytest.raises(ValidationError, match="increasing date order"):
        LogWeekDTO.model_validate(_week(days=[_day("2026-10-13"), _day("2026-10-13")]))
