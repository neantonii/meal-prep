"""Tests for writing a plan into the diary and taking it back
(``services/prep.py``, "Planner"; ``docs/planner.md``)."""

from __future__ import annotations

import uuid

import pytest

from meal_prep.dtos.log import RecipeEntryDTO
from meal_prep.enums import Mealtime
from meal_prep.services import prep
from meal_prep.services.prep import (
    Diary,
    PlannedCook,
    PlannedMeal,
    RuleError,
)
from tests.meal_prep.services.test_prep import (
    CHICKEN,
    EGG,
    EMPTY,
    PLAN,
    RECIPES,
    SUN,
    THU,
    TUE,
    YESTERDAY,
    D,
    _add,
    _apply,
)

LUNCH, DINNER = Mealtime.LUNCH, Mealtime.DINNER
FRI, SAT = D(2026, 11, 6), D(2026, 11, 7)


def _day_meals(diary: Diary) -> list[RecipeEntryDTO]:
    return [link.entry for link in prep.linked_entries(diary.weeks.values())]


def _plan(diary: Diary = EMPTY) -> Diary:
    # Thursday cooks 1 batch of chicken (4 portions), eats 3; Sunday cooks
    # one egg.
    change = prep.apply_plan(
        diary,
        PLAN,
        RECIPES,
        cooks=[PlannedCook(THU, "chicken", 1), PlannedCook(SUN, "egg", 1)],
        meals=[
            PlannedMeal(THU, DINNER, "chicken", THU),
            PlannedMeal(FRI, LUNCH, "chicken", THU),
            PlannedMeal(SAT, LUNCH, "chicken", THU),
            PlannedMeal(SUN, DINNER, "egg", SUN),
        ],
    )
    return _apply(diary, change)


def test_a_plan_writes_sessions_meals_and_leftovers_flagged():
    diary = _plan()
    by_date = {s.date: s for s in diary.sessions.values()}
    assert [(i.recipe, i.batches) for i in by_date[THU].items] == [("chicken", 1)]
    assert [(i.recipe, i.batches) for i in by_date[SUN].items] == [("egg", 1)]
    meals = _day_meals(diary)
    assert len(meals) == 4 and all(m.planned for m in meals)
    # The fourth chicken portion has no day: unassigned, still flagged.
    assert [(m.recipe, m.planned) for m in diary.unassigned] == [("chicken", True)]


def test_a_plan_adds_to_an_existing_session_and_after_existing_meals():
    diary, manual = _add(EMPTY, THU, CHICKEN, meal=DINNER)  # 1 batch by hand
    diary = _plan(diary)
    (thursday,) = [s for s in diary.sessions.values() if s.date == THU]
    assert [(i.recipe, i.batches) for i in thursday.items] == [("chicken", 2)]
    dinner = [
        link.entry.id
        for link in prep.linked_entries(diary.weeks.values())
        if link.date == THU and link.mealtime == DINNER
    ]
    assert dinner[0] == manual.id  # the manual meal stays first


def test_a_plan_cannot_touch_a_cooked_session():
    with pytest.raises(RuleError, match="already cooked"):
        prep.apply_plan(EMPTY, PLAN, RECIPES, [PlannedCook(YESTERDAY, "egg", 1)], [])


def test_moving_a_planned_meal_onto_a_day_makes_it_manual():
    diary = _plan()
    meal = next(m for m in _day_meals(diary) if m.recipe == "chicken")
    diary = _apply(diary, prep.move_meal(diary, PLAN, meal.id, prep.Day(SAT, DINNER)))
    moved = next(m for m in _day_meals(diary) if m.id == meal.id)
    assert not moved.planned


def test_clear_plans_removes_planned_meals_and_their_batches():
    diary = _plan()
    cleared = _apply(diary, prep.clear_plans(diary, PLAN))
    assert cleared.sessions == {}
    assert _day_meals(cleared) == []
    assert list(cleared.unassigned) == []


def test_clear_plans_keeps_manual_meals_and_what_they_need():
    diary, manual = _add(EMPTY, THU, CHICKEN, meal=DINNER)  # 4 portions by hand
    diary = _plan(diary)
    # One planned portion was moved by hand onto a day: it is manual now.
    planned = next(m for m in _day_meals(diary) if m.planned and m.recipe == "chicken")
    diary = _apply(
        diary, prep.move_meal(diary, PLAN, planned.id, prep.Day(SAT, DINNER))
    )
    cleared = _apply(diary, prep.clear_plans(diary, PLAN))
    (thursday,) = cleared.sessions.values()
    # 4 manual portions + 1 adopted = 5 meals: 2 batches of 4, 3 refilled.
    assert [(i.recipe, i.batches) for i in thursday.items] == [("chicken", 2)]
    assert {m.id for m in _day_meals(cleared)} == {manual.id, planned.id}
    assert sum(1 for m in cleared.unassigned if m.recipe == "chicken") == 6
    assert not any(m.planned for m in cleared.unassigned)


def test_clear_plans_leaves_cooked_sessions_alone():
    diary = _plan()
    later = prep.Policy(today=FRI)  # both sessions are cooked by then
    assert prep.clear_plans(diary, later) == prep.Change()


def test_accept_makes_a_sessions_meals_manual():
    diary = _plan()
    thursday = next(s.id for s in diary.sessions.values() if s.date == THU)
    accepted = _apply(diary, prep.accept_session(diary, PLAN, thursday))
    flags = {(m.recipe, bool(m.planned)) for m in _day_meals(accepted)}
    assert flags == {("chicken", False), ("egg", True)}
    assert not any(m.planned for m in accepted.unassigned)
    # Clear plans now keeps Thursday entirely.
    cleared = _apply(accepted, prep.clear_plans(accepted, PLAN))
    assert [s.date for s in cleared.sessions.values()] == [THU]


def test_accept_an_unknown_session_is_an_error():
    with pytest.raises(prep.SessionNotFoundError):
        prep.accept_session(EMPTY, PLAN, uuid.uuid4())


def test_planned_meals_never_outnumber_portions():
    with pytest.raises(RuleError, match="more egg"):
        prep.apply_plan(
            EMPTY,
            PLAN,
            RECIPES,
            [PlannedCook(TUE, "egg", 1)],
            [PlannedMeal(TUE, DINNER, "egg", TUE), PlannedMeal(THU, LUNCH, "egg", TUE)],
        )
    assert EGG.servings == 1


def test_clear_plans_leaves_manual_sessions_with_spares_alone():
    # An older file: 1 batch of chicken (4 portions), only 1 meal recorded.
    diary, _ = _add(EMPTY, THU, CHICKEN, meal=DINNER)
    diary = Diary(weeks=diary.weeks, sessions=diary.sessions)  # no unassigned
    assert prep.clear_plans(diary, PLAN) == prep.Change()
