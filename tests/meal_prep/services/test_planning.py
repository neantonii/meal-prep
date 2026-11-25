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
    # The plan ate the 3 unassigned manual portions first; one was adopted,
    # the other 2 go back. The plan's own batch goes: 4 meals, 1 batch.
    assert [(i.recipe, i.batches) for i in thursday.items] == [("chicken", 1)]
    assert {m.id for m in _day_meals(cleared)} == {manual.id, planned.id}
    assert sum(1 for m in cleared.unassigned if m.recipe == "chicken") == 2
    assert not any(m.planned for m in cleared.unassigned)
    assert thursday.items[0].planned_batches is None


def test_a_plan_records_its_batches_on_the_recipe_line():
    diary, _ = _add(EMPTY, THU, CHICKEN, meal=DINNER)  # 1 batch by hand
    diary = _plan(diary)
    thursday = next(s for s in diary.sessions.values() if s.date == THU)
    (line,) = thursday.items
    assert (line.batches, line.planned_batches) == (2, 1)
    # Accepting makes the batch yours.
    accepted = _apply(diary, prep.accept_session(diary, PLAN, thursday.id))
    (line,) = accepted.sessions[thursday.id].items
    assert (line.batches, line.planned_batches) == (2, None)


def test_removing_a_batch_takes_back_a_planned_one_first():
    diary = _plan()  # Thursday: 1 planned chicken batch, 3 eaten, 1 unassigned
    thursday = next(s for s in diary.sessions.values() if s.date == THU)
    # Two adds by hand: 2 batches, 1 of them planned.
    diary, _ = _add(diary, THU, CHICKEN, session=thursday.id, meal=DINNER)
    (line,) = diary.sessions[thursday.id].items
    assert (line.batches, line.planned_batches) == (2, 1)
    # Free the planned portions, then remove a batch: the planned one goes.
    for meal in [m for m in _day_meals(diary) if m.planned]:
        diary = _apply(diary, prep.move_meal(diary, PLAN, meal.id, "unassigned"))
    diary = _apply(diary, prep.remove_batch(diary, PLAN, thursday.id, "chicken"))
    (line,) = diary.sessions[thursday.id].items
    assert (line.batches, line.planned_batches) == (1, None)


def test_a_plan_uses_unassigned_portions_first_and_clear_puts_them_back():
    diary, _ = _add(EMPTY, THU, CHICKEN, meal=DINNER)  # 1 on Thu, 3 unassigned
    stock = {m.id for m in diary.unassigned}
    change = prep.apply_plan(
        diary,
        PLAN,
        RECIPES,
        cooks=[],
        meals=[
            PlannedMeal(FRI, LUNCH, "chicken", THU),
            PlannedMeal(SAT, LUNCH, "chicken", THU),
        ],
    )
    planned = _apply(diary, change)
    placed = [m for m in _day_meals(planned) if m.planned]
    assert {m.id for m in placed} <= stock  # existing portions, no new batch
    assert all(m.planned for m in placed)
    (thursday,) = planned.sessions.values()
    assert thursday.items[0].batches == 1
    assert len(planned.unassigned) == 1

    cleared = _apply(planned, prep.clear_plans(planned, PLAN))
    assert {m.id for m in cleared.unassigned} == stock
    assert not any(m.planned for m in cleared.unassigned)
    assert cleared.sessions == planned.sessions


def test_clear_puts_back_portions_of_cooked_sessions_too():
    diary, _ = _add(EMPTY, THU, CHICKEN, meal=DINNER)
    change = prep.apply_plan(
        diary, PLAN, RECIPES, cooks=[], meals=[PlannedMeal(SAT, LUNCH, "chicken", THU)]
    )
    planned = _apply(diary, change)
    later = prep.Policy(today=FRI)  # Thursday's session is cooked by then
    cleared = _apply(planned, prep.clear_plans(planned, later))
    assert len(cleared.unassigned) == 3
    assert not any(m.planned for m in _day_meals(cleared))


def test_clear_plans_keeps_cooked_batches_and_past_days():
    diary = _plan()
    later = prep.Policy(today=FRI)  # both sessions cooked; Thursday is past
    cleared = _apply(diary, prep.clear_plans(diary, later))
    # Cooked batches are facts: no session loses a batch.
    batches = {
        (s.date, i.recipe): (i.batches, i.planned_batches)
        for s in cleared.sessions.values()
        for i in s.items
    }
    assert batches == {(THU, "chicken"): (1, None), (SUN, "egg"): (1, None)}
    # Thursday's dinner is history and stays; Friday on goes back.
    days = {
        (link.date, link.entry.recipe)
        for link in prep.linked_entries(cleared.weeks.values())
    }
    assert (THU, "chicken") in days
    assert (FRI, "chicken") not in days
    assert sum(1 for m in cleared.unassigned if m.recipe == "chicken") == 3


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
