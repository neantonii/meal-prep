"""Free-form diary entries (takeout, eating out; #142): the format, the
numbers kept for the share eaten, the rules, and repeats from history."""

from __future__ import annotations

import datetime
import uuid

import pytest
from pydantic import ValidationError

from meal_prep.dtos.log import DiaryEntryDTO, DiaryWeekDTO, EntryEstimateDTO
from meal_prep.enums import Mealtime
from meal_prep.services import diary, prep
from meal_prep.services.logs import prepare_diary_week
from meal_prep.services.prep import Diary, Policy, RuleError

D = datetime.date
TODAY = D(2026, 11, 5)
WEEK = "2026-W45"
FRI, SAT = D(2026, 11, 6), D(2026, 11, 7)
PLAN = Policy(today=TODAY)
MEAL = {"calories_kcal": 1008.0, "protein_g": 35.0, "cost": 14.0}


def _week(*placed: tuple[D, Mealtime, DiaryEntryDTO]) -> DiaryWeekDTO | None:
    week: DiaryWeekDTO | None = None
    for date, mealtime, entry in placed:
        week, _ = diary.insert_entry(week, WEEK, date, mealtime, entry)
    return week


def test_a_free_form_entry_keeps_the_share_eaten_and_unknowns():
    entry = diary.free_entry("McChicken meal", MEAL, portion=0.5)
    assert entry.recipe is None and entry.free_form
    assert (entry.calories_kcal, entry.protein_g, entry.cost) == (504, 17.5, 7)
    assert entry.fat_g is None and entry.portion == 0.5
    whole = diary.free_entry("Pho", {"calories_kcal": 700.0})
    assert whole.portion is None  # the whole order: not written
    with pytest.raises(ValueError, match="Unknown numbers"):
        diary.free_entry("Pho", {"kcal": 700.0})


def test_the_format_keeps_recipe_entries_complete_and_free_ones_unlinked():
    base = {"id": uuid.uuid4(), "title": "Pho"}
    DiaryEntryDTO.model_validate(base)  # free-form, every number unknown
    with pytest.raises(ValidationError, match="never linked"):
        DiaryEntryDTO.model_validate({**base, "session": uuid.uuid4()})
    with pytest.raises(ValidationError, match="missing"):
        DiaryEntryDTO.model_validate({**base, "recipe": "pho", "cost": 1})
    numbers = dict.fromkeys(
        ("cost", "calories_kcal", "protein_g", "fat_g", "carbs_g", "fiber_g"), 1
    ) | dict.fromkeys(("saturated_fat_g", "sugars_g", "sodium_mg", "potassium_mg"), 1)
    DiaryEntryDTO.model_validate({**base, "recipe": "pho", **numbers})
    with pytest.raises(ValidationError, match="portion or estimate"):
        DiaryEntryDTO.model_validate(
            {**base, "recipe": "pho", **numbers, "portion": 0.5}
        )


def test_totals_leave_unknowns_out_and_say_so():
    guess = EntryEstimateDTO(source="manual")
    week = _week(
        (FRI, Mealtime.LUNCH, diary.free_entry("Pho", MEAL, estimate=guess)),
        (SAT, Mealtime.LUNCH, diary.free_entry("Burger", {"cost": 12.0})),
    )
    assert week is not None
    fri, sat = prepare_diary_week(week).days
    assert fri.macros.calories_kcal == 1008 and fri.estimated
    assert "fat_g" in fri.unknown and "calories_kcal" not in fri.unknown
    assert sat.macros.calories_kcal == 0 and "calories_kcal" in sat.unknown
    assert not sat.estimated


def test_free_form_entries_never_link_to_a_session():
    entry = diary.free_entry("Pho", MEAL)
    change = prep.add_free_entry(Diary({}, {}), PLAN, WEEK, FRI, Mealtime.LUNCH, entry)
    assert change.sessions == {}  # no session created, unlike a recipe drop
    state = Diary(weeks={WEEK: change.weeks[WEEK]}, sessions={})  # type: ignore[dict-item]
    with pytest.raises(RuleError, match="never linked"):
        prep.set_entry_session(state, PLAN, {}, WEEK, entry.id, None, TODAY)
    assert prep.set_entry_session(state, PLAN, {}, WEEK, entry.id, None) == (
        prep.Change()
    )
    moved = prep.move_entry(state, PLAN, {}, WEEK, entry.id, SAT, Mealtime.DINNER)
    assert moved.sessions == {}


def test_only_free_form_numbers_can_be_edited_and_settled_meals_are_locked():
    entry = diary.free_entry("Pho", MEAL)
    week = _week((FRI, Mealtime.LUNCH, entry))
    assert week is not None
    state = Diary(weeks={WEEK: week}, sessions={})
    fixed = diary.free_entry("Pho, large", {"calories_kcal": 850.0}, entry_id=entry.id)
    change = prep.edit_free_entry(state, PLAN, WEEK, fixed)
    [day] = change.weeks[WEEK].days  # type: ignore[union-attr]
    assert day.lunch == [fixed]
    # Two cycles later, Friday's lunch is settled: Admin only.
    later = Policy(today=D(2026, 11, 11))
    with pytest.raises(RuleError, match="settled"):
        prep.edit_free_entry(state, later, WEEK, fixed)
    with pytest.raises(RuleError, match="settled"):
        prep.add_free_entry(state, later, WEEK, FRI, Mealtime.DINNER, fixed)


def test_history_offers_each_meal_once_with_its_latest_whole_order():
    week = _week(
        (FRI, Mealtime.LUNCH, diary.free_entry("McChicken meal", MEAL)),
        (FRI, Mealtime.DINNER, diary.free_entry("Pho", {"calories_kcal": 700.0})),
        (
            SAT,
            Mealtime.LUNCH,
            diary.free_entry(
                " mcchicken  MEAL", {**MEAL, "calories_kcal": 1200.0}, portion=0.5
            ),
        ),
    )
    assert week is not None
    usuals = diary.free_form_history([week])
    assert [(u.title, u.times, u.last) for u in usuals] == [
        ("mcchicken MEAL", 2, SAT),  # Saturday's spelling, tidied: the latest
        ("Pho", 1, FRI),
    ]
    # Saturday's half portion, scaled back to the whole order.
    assert usuals[0].order["calories_kcal"] == 1200
    assert usuals[0].order["fat_g"] is None
