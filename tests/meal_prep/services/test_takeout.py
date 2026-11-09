"""Takeout diary entries (#142): the two entry types, the rules, and
repeats from history."""

from __future__ import annotations

import datetime
import uuid

import pytest
from pydantic import TypeAdapter, ValidationError

from meal_prep.dtos.log import (
    DiaryEntryDTO,
    DiaryWeekDTO,
    RecipeEntryDTO,
    TakeoutEntryDTO,
)
from meal_prep.enums import Mealtime
from meal_prep.models.log import TakeoutLogEntry
from meal_prep.services import diary, prep
from meal_prep.services.logs import prepare_diary_week
from meal_prep.services.prep import Diary, Policy, RuleError

D = datetime.date
TODAY = D(2026, 11, 5)
WEEK = "2026-W45"
FRI, SAT = D(2026, 11, 6), D(2026, 11, 7)
PLAN = Policy(today=TODAY)
ENTRY = TypeAdapter(DiaryEntryDTO)
MACROS = {"calories_kcal": 480.0, "protein_g": 16.0, "carbs_g": 45.0, "fat_g": 27.0}


def _takeout(title: str = "McChicken", kcal: float = 480.0, **extra) -> TakeoutEntryDTO:
    return diary.takeout_entry(
        title, calories_kcal=kcal, protein_g=16, carbs_g=45, fat_g=27, **extra
    )


def _week(*placed: tuple[D, Mealtime, TakeoutEntryDTO]) -> DiaryWeekDTO | None:
    week: DiaryWeekDTO | None = None
    for date, mealtime, entry in placed:
        week, _ = diary.insert_entry(week, WEEK, date, mealtime, entry)
    return week


def test_an_entry_is_a_recipe_serving_or_takeout_by_whether_it_names_a_recipe():
    base = {"id": uuid.uuid4(), "title": "Pho", **MACROS}
    assert isinstance(ENTRY.validate_python(base), TakeoutEntryDTO)
    extras = dict.fromkeys(
        ("cost", "fiber_g", "saturated_fat_g", "sugars_g", "sodium_mg"), 1
    ) | {"potassium_mg": 1}
    recipe = ENTRY.validate_python({**base, "recipe": "pho", **extras})
    assert isinstance(recipe, RecipeEntryDTO)
    # Takeout can't link to a session, and needs calories and macros...
    with pytest.raises(ValidationError, match="session"):
        ENTRY.validate_python({**base, "session": str(uuid.uuid4())})
    with pytest.raises(ValidationError, match="protein_g"):
        ENTRY.validate_python({"id": uuid.uuid4(), "title": "Pho", "calories_kcal": 1})
    # ...a recipe entry needs every number.
    with pytest.raises(ValidationError, match="cost"):
        ENTRY.validate_python({**base, "recipe": "pho"})


def test_takeout_tidies_its_title_and_keeps_cost_only_if_known():
    entry = _takeout("  McDonald's   McChicken ")
    assert entry.title == "McDonald's McChicken"
    assert (entry.calories_kcal, entry.cost, entry.fiber_g) == (480, None, None)
    assert _takeout(cost=7.5).cost == 7.5


def test_an_unknown_cost_counts_as_zero_in_totals():
    week = _week(
        (FRI, Mealtime.LUNCH, _takeout("Pho", cost=12.0)),
        (FRI, Mealtime.DINNER, _takeout("Burger")),
    )
    assert week is not None
    [fri] = prepare_diary_week(week).days
    assert fri.macros.calories_kcal == 960 and fri.cost == 12
    assert all(isinstance(e, TakeoutLogEntry) for e in fri.entries())


def test_takeout_never_links_to_a_session():
    entry = _takeout()
    change = prep.add_takeout_entries(
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
    items = [_takeout(name) for name in ("Burger", "Fries", "Drink")]
    change = prep.add_takeout_entries(
        Diary({}, {}), PLAN, WEEK, FRI, Mealtime.LUNCH, items
    )
    [day] = change.weeks[WEEK].days  # type: ignore[union-attr]
    assert [e.title for e in day.lunch or ()] == ["Burger", "Fries", "Drink"]


def test_only_takeout_can_be_edited_and_settled_meals_are_locked():
    entry = _takeout("Pho")
    week = _week((FRI, Mealtime.LUNCH, entry))
    assert week is not None
    state = Diary(weeks={WEEK: week}, sessions={})
    fixed = _takeout("Large Pho", kcal=850, entry_id=entry.id)
    change = prep.edit_takeout_entry(state, PLAN, WEEK, fixed)
    [day] = change.weeks[WEEK].days  # type: ignore[union-attr]
    assert day.lunch == [fixed]
    # Two cycles later, Friday's lunch is settled: Admin only.
    later = Policy(today=D(2026, 11, 11))
    with pytest.raises(RuleError, match="settled"):
        prep.edit_takeout_entry(state, later, WEEK, fixed)
    with pytest.raises(RuleError, match="settled"):
        prep.add_takeout_entries(state, later, WEEK, FRI, Mealtime.DINNER, [fixed])


def test_history_offers_each_meal_once_with_its_latest_entry():
    week = _week(
        (FRI, Mealtime.LUNCH, _takeout("McChicken", cost=7.5)),
        (FRI, Mealtime.DINNER, _takeout("Pho")),
        (SAT, Mealtime.LUNCH, _takeout(" mcchicken ", kcal=470)),
    )
    assert week is not None
    usuals = diary.takeout_history([week])
    assert [(u.entry.title, u.times, u.last) for u in usuals] == [
        ("mcchicken", 2, SAT),  # Saturday's spelling: the latest
        ("Pho", 1, FRI),
    ]
    assert usuals[0].entry.calories_kcal == 470
    assert usuals[0].entry.cost is None
