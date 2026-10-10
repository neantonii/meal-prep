"""Tests for the log DTOs (``dtos/log.py``).

Happy paths plus our custom validation only. Pydantic's implicit field
constraints (``pattern``, ``min_length``, enum coercion) are not re-tested.

Our custom validation in this module:
- ``LogDayDTO.validate_slot_order`` -> dedupes by mealtime, sorts to enum order
- ``LogWeekDTO.validate_day_order`` -> strictly increasing dates
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from meal_prep.dtos.log import LogDayDTO, LoggedSlotDTO, LogWeekDTO
from meal_prep.enums import Mealtime


def _slot(mealtime: str = "breakfast", recipes: list[str] | None = None):
    return {"mealtime": mealtime, "recipes": recipes or ["oatmeal"]}


def _day(day: str = "2026-10-13", slots: list | None = None):
    return {"date": day, "slots": slots if slots is not None else [_slot()]}


def _week(**overrides):
    data = {"week": "2026-W42", "days": [_day()]}
    data.update(overrides)
    return data


def test_logged_slot_valid():
    slot = LoggedSlotDTO.model_validate(_slot())
    assert slot.mealtime is Mealtime.BREAKFAST
    assert slot.recipes == ["oatmeal"]


def test_logged_slot_recipe_ids_are_normalized():
    slot = LoggedSlotDTO.model_validate(_slot(recipes=["  Oatmeal  "]))
    assert slot.recipes == ["oatmeal"]


def test_logged_slot_rejects_unknown_mealtime():
    with pytest.raises(ValidationError):
        LoggedSlotDTO.model_validate(_slot(mealtime="brunch"))


def test_log_day_sorts_slots_to_mealtime_order():
    day = LogDayDTO.model_validate(
        _day(slots=[_slot("dinner"), _slot("breakfast"), _slot("snacks")])
    )
    assert [s.mealtime for s in day.slots] == [
        Mealtime.BREAKFAST,
        Mealtime.DINNER,
        Mealtime.SNACKS,
    ]


def test_log_day_rejects_duplicate_mealtime():
    with pytest.raises(ValidationError, match="Duplicate mealtime"):
        LogDayDTO.model_validate(_day(slots=[_slot("lunch"), _slot("lunch")]))


def test_log_week_valid():
    week = LogWeekDTO.model_validate(_week())
    assert week.week == "2026-W42"
    assert len(week.days) == 1
    assert week.source_path is None


def test_log_week_rejects_bad_week_label():
    with pytest.raises(ValidationError):
        LogWeekDTO.model_validate(_week(week="october"))


def test_log_week_rejects_unordered_days():
    with pytest.raises(ValidationError, match="increasing date order"):
        LogWeekDTO.model_validate(_week(days=[_day("2026-10-14"), _day("2026-10-13")]))


def test_log_week_rejects_duplicate_dates():
    with pytest.raises(ValidationError, match="increasing date order"):
        LogWeekDTO.model_validate(_week(days=[_day("2026-10-13"), _day("2026-10-13")]))
