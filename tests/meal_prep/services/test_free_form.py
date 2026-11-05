"""Free-form diary entries (takeout, eating out; #142): the format, the
rules, and repeats from history."""

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
MACROS = {"calories_kcal": 480.0, "protein_g": 16.0, "carbs_g": 45.0, "fat_g": 27.0}
MEAL = {**MACROS, "cost": 7.5}


def _week(*placed: tuple[D, Mealtime, DiaryEntryDTO]) -> DiaryWeekDTO | None:
    week: DiaryWeekDTO | None = None
    for date, mealtime, entry in placed:
        week, _ = diary.insert_entry(week, WEEK, date, mealtime, entry)
    return week


def test_a_free_form_entry_needs_calories_and_macros_only():
    entry = diary.free_entry("  McDonald's   McChicken ", MEAL)
    assert entry.recipe is None and entry.free_form
    assert entry.title == "McDonald's McChicken"  # spacing tidied
    assert (entry.calories_kcal, entry.cost, entry.fiber_g) == (480, 7.5, None)
    with pytest.raises(ValidationError, match="missing protein_g"):
        diary.free_entry("Pho", {"calories_kcal": 700.0})
    with pytest.raises(ValueError, match="Unknown numbers"):
        diary.free_entry("Pho", {**MACROS, "kcal": 700.0})


def test_the_format_keeps_recipe_entries_complete_and_free_ones_unlinked():
    base = {"id": uuid.uuid4(), "title": "Pho", **MACROS}
    DiaryEntryDTO.model_validate(base)  # free-form: cost, fiber... unknown
    with pytest.raises(ValidationError, match="never linked"):
        DiaryEntryDTO.model_validate({**base, "session": uuid.uuid4()})
    with pytest.raises(ValidationError, match="Free-form entry is missing"):
        DiaryEntryDTO.model_validate({"id": uuid.uuid4(), "title": "Pho"})
    with pytest.raises(ValidationError, match="Recipe entry is missing"):
        DiaryEntryDTO.model_validate({**base, "recipe": "pho"})
    numbers = dict.fromkeys(
        ("cost", "fiber_g", "saturated_fat_g", "sugars_g", "sodium_mg"), 1
    ) | {"potassium_mg": 1}
    DiaryEntryDTO.model_validate({**base, "recipe": "pho", **numbers})
    with pytest.raises(ValidationError, match="Only free-form entries"):
        DiaryEntryDTO.model_validate(
            {
                **base,
                "recipe": "pho",
                **numbers,
                "estimate": EntryEstimateDTO(source="manual"),
            }
        )


def test_totals_mark_guesses_and_an_unknown_cost():
    guess = EntryEstimateDTO(source="manual")
    week = _week(
        (FRI, Mealtime.LUNCH, diary.free_entry("Pho", MEAL, estimate=guess)),
        (SAT, Mealtime.LUNCH, diary.free_entry("Burger", MACROS)),
    )
    assert week is not None
    fri, sat = prepare_diary_week(week).days
    assert fri.macros.calories_kcal == 480 and fri.estimated
    assert "calories_kcal" not in fri.unknown
    assert "cost" in sat.unknown and not sat.estimated


def test_free_form_entries_never_link_to_a_session():
    entry = diary.free_entry("Pho", MEAL)
    change = prep.add_free_entries(
        Diary({}, {}), PLAN, WEEK, FRI, Mealtime.LUNCH, [entry]
    )
    assert change.sessions == {}  # no session created, unlike a recipe drop
    state = Diary(weeks={WEEK: change.weeks[WEEK]}, sessions={})  # type: ignore[dict-item]
    with pytest.raises(RuleError, match="never linked"):
        prep.set_entry_session(state, PLAN, {}, WEEK, entry.id, None, TODAY)
    assert prep.set_entry_session(state, PLAN, {}, WEEK, entry.id, None) == (
        prep.Change()
    )
    moved = prep.move_entry(state, PLAN, {}, WEEK, entry.id, SAT, Mealtime.DINNER)
    assert moved.sessions == {}


def test_a_whole_order_is_added_in_order():
    items = [diary.free_entry(name, MACROS) for name in ("Burger", "Fries", "Drink")]
    change = prep.add_free_entries(
        Diary({}, {}), PLAN, WEEK, FRI, Mealtime.LUNCH, items
    )
    [day] = change.weeks[WEEK].days  # type: ignore[union-attr]
    assert [e.title for e in day.lunch or ()] == ["Burger", "Fries", "Drink"]


def test_only_free_form_numbers_can_be_edited_and_settled_meals_are_locked():
    entry = diary.free_entry("Pho", MEAL)
    week = _week((FRI, Mealtime.LUNCH, entry))
    assert week is not None
    state = Diary(weeks={WEEK: week}, sessions={})
    fixed = diary.free_entry(
        "Pho, large", {**MACROS, "calories_kcal": 850.0}, entry_id=entry.id
    )
    change = prep.edit_free_entry(state, PLAN, WEEK, fixed)
    [day] = change.weeks[WEEK].days  # type: ignore[union-attr]
    assert day.lunch == [fixed]
    # Two cycles later, Friday's lunch is settled: Admin only.
    later = Policy(today=D(2026, 11, 11))
    with pytest.raises(RuleError, match="settled"):
        prep.edit_free_entry(state, later, WEEK, fixed)
    with pytest.raises(RuleError, match="settled"):
        prep.add_free_entries(state, later, WEEK, FRI, Mealtime.DINNER, [fixed])


def test_history_offers_each_meal_once_with_its_latest_numbers():
    week = _week(
        (FRI, Mealtime.LUNCH, diary.free_entry("McChicken", MEAL)),
        (FRI, Mealtime.DINNER, diary.free_entry("Pho", MACROS)),
        (
            SAT,
            Mealtime.LUNCH,
            diary.free_entry(" mcchicken ", {**MEAL, "calories_kcal": 470.0}),
        ),
    )
    assert week is not None
    usuals = diary.free_form_history([week])
    assert [(u.title, u.times, u.last) for u in usuals] == [
        ("mcchicken", 2, SAT),  # Saturday's spelling: the latest
        ("Pho", 1, FRI),
    ]
    assert usuals[0].numbers["calories_kcal"] == 470
    assert usuals[0].numbers["fiber_g"] is None
