"""Tests for the diary DTOs (``dtos/log.py``).

Happy paths plus our custom validation only. Pydantic's implicit field
constraints (``pattern``, ``min_length``, enum coercion) are not re-tested.

Our custom validation in this module:
- ``DiaryDayDTO.validate_at_least_one_meal`` -> no empty days
- ``DiaryWeekDTO.validate_day_order`` -> strictly increasing dates
- ``DiaryWeekDTO.validate_days_in_week`` -> real ISO week, days inside it
- ``DiaryWeekDTO.validate_unique_entry_ids`` -> no entry id twice in a week
- ``DiaryEntryDTO.validate_recipe_id`` -> normalizes the recipe slug
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from meal_prep.dtos.log import DiaryDayDTO, DiaryEntryDTO, DiaryWeekDTO


def _entry(recipe: str = "oatmeal", entry_id: str | None = None) -> dict:
    return {
        "id": entry_id or str(uuid.uuid4()),
        "recipe": recipe,
        "title": "Oatmeal",
        "cost": 1.25,
        "calories_kcal": 310.5,
        "protein_g": 12.0,
        "fat_g": 8.0,
        "carbs_g": 45.0,
        "fiber_g": 6.0,
        "saturated_fat_g": 1.5,
        "sugars_g": 9.0,
        "sodium_mg": 120.0,
        "potassium_mg": 300.0,
    }


def _day(day: str = "2026-10-13", **meals) -> dict:
    data: dict = {"date": day}
    data.update(meals or {"breakfast": [_entry()]})
    return data


def _week(**overrides) -> dict:
    data = {"week": "2026-W42", "days": [_day()]}
    data.update(overrides)
    return data


def test_diary_week_valid():
    diary = DiaryWeekDTO.model_validate(_week())
    breakfast = diary.days[0].breakfast
    assert breakfast is not None
    assert breakfast[0].recipe == "oatmeal"
    assert breakfast[0].calories_kcal == 310.5
    assert diary.days[0].lunch is None
    assert diary.days[0].entries() == breakfast


def test_entry_recipe_id_is_normalized():
    assert DiaryEntryDTO.model_validate(_entry(recipe="  Oatmeal ")).recipe == "oatmeal"


def test_rejects_bare_recipe_ids():
    with pytest.raises(ValidationError):
        DiaryWeekDTO.model_validate(_week(days=[_day(breakfast=["oatmeal"])]))


def test_entry_requires_frozen_numbers():
    data = _entry()
    del data["cost"]
    with pytest.raises(ValidationError):
        DiaryEntryDTO.model_validate(data)


def test_entry_rejects_non_uuid_id():
    with pytest.raises(ValidationError):
        DiaryEntryDTO.model_validate(_entry(entry_id="not-a-uuid"))


def test_day_rejects_empty_meal_list():
    with pytest.raises(ValidationError):
        DiaryDayDTO.model_validate(_day(breakfast=[]))


def test_day_rejects_unknown_field():
    with pytest.raises(ValidationError):
        DiaryDayDTO.model_validate(_day(brunch=[_entry()]))


def test_day_rejects_day_without_meals():
    with pytest.raises(ValidationError, match="at least one mealtime"):
        DiaryDayDTO.model_validate({"date": "2026-10-13"})


def test_week_rejects_duplicate_entry_ids():
    same = str(uuid.uuid4())
    day = _day(breakfast=[_entry(entry_id=same), _entry(entry_id=same)])
    with pytest.raises(ValidationError, match="Duplicate entry id"):
        DiaryWeekDTO.model_validate(_week(days=[day]))


@pytest.mark.parametrize("label", ["october", "2026-W42\n", "2026-w42"])
def test_week_rejects_bad_week_label(label: str):
    with pytest.raises(ValidationError):
        DiaryWeekDTO.model_validate(_week(week=label))


def test_week_rejects_unordered_days():
    with pytest.raises(ValidationError, match="increasing date order"):
        DiaryWeekDTO.model_validate(
            _week(days=[_day("2026-10-14"), _day("2026-10-13")])
        )


def test_week_rejects_duplicate_dates():
    with pytest.raises(ValidationError, match="increasing date order"):
        DiaryWeekDTO.model_validate(
            _week(days=[_day("2026-10-13"), _day("2026-10-13")])
        )


def test_week_rejects_nonexistent_week_number():
    with pytest.raises(ValidationError, match="not a real ISO week"):
        DiaryWeekDTO.model_validate(_week(week="2026-W99"))


def test_week_rejects_week_53_in_a_52_week_year():
    # 2026 has 53 ISO weeks, 2025 only 52.
    DiaryWeekDTO.model_validate(_week(week="2026-W53", days=[_day("2026-12-31")]))
    with pytest.raises(ValidationError, match="not a real ISO week"):
        DiaryWeekDTO.model_validate(_week(week="2025-W53", days=[_day("2025-12-31")]))


def test_week_rejects_day_outside_its_week():
    # 2026-W42 is Mon 2026-10-12 .. Sun 2026-10-18.
    DiaryWeekDTO.model_validate(_week(days=[_day("2026-10-12"), _day("2026-10-18")]))
    with pytest.raises(ValidationError, match="outside ISO week 2026-W42"):
        DiaryWeekDTO.model_validate(_week(days=[_day("2026-10-19")]))


def test_entry_session_link_is_optional():
    assert DiaryEntryDTO.model_validate(_entry()).session is None
    session = uuid.uuid4()
    linked = DiaryEntryDTO.model_validate({**_entry(), "session": str(session)})
    assert linked.session == session
    assert "session" not in DiaryEntryDTO.model_validate(_entry()).model_dump(
        exclude_none=True
    )
