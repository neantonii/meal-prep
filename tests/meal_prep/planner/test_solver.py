"""Tests for the planner's solver (``meal_prep/planner/solver.py``).

All recipes are hand-built fakes, so the best plan is known exactly.
"""

from __future__ import annotations

import datetime

import pytest

from meal_prep.enums import Aisle, Mealtime, RecipeCategory, StorageType
from meal_prep.models.ingredient import MacrosInfo, Package
from meal_prep.models.recipe import Recipe, RecipeIngredient
from meal_prep.planner.plan import (
    TAKEOUT,
    Archetype,
    Batch,
    Pin,
    Plan,
    Problem,
    Role,
    Slot,
    Weights,
    single,
    split,
)
from meal_prep.planner.solver import plan

P = RecipeCategory.MODULAR_PROTEIN
C = RecipeCategory.MODULAR_CARB
V = RecipeCategory.MODULAR_COOKED_VEG
D = RecipeCategory.ONE_DISH
THU = datetime.date(2026, 11, 5)
LUNCH = Mealtime.LUNCH


def _macros(*, cal: float = 100.0, protein: float = 10.0) -> MacrosInfo:
    return MacrosInfo(
        calories_kcal=cal,
        protein_g=protein,
        fat_g=5.0,
        carbs_g=20.0,
        fiber_g=1.0,
        saturated_fat_g=0.0,
        sugars_g=0.0,
        sodium_mg=0.0,
        potassium_mg=0.0,
    )


def _recipe(
    recipe_id: str,
    category: RecipeCategory = RecipeCategory.MODULAR_PROTEIN,
    *,
    servings: float = 1.0,
    cost: float = 1.0,
) -> Recipe:
    return Recipe(
        id=recipe_id,
        title=f"Recipe {recipe_id}",
        category=category,
        servings=servings,
        cooked_g=200.0,
        fridge_days=4,
        freezer_friendly=True,
        equipment=(),
        cookware_by_token={},
        ingredients=(
            RecipeIngredient(
                id="a",
                name="A",
                step_name="a",
                aisle=Aisle.MEAT,
                storage=StorageType.REFRIGERATED,
                shelf_life_days=3,
                quantity=200.0,
                unit="g",
                grams=200.0,
                cost=cost,
                macros=_macros(),
                package=Package("Test 1 kg", 1.0, "kg", 1000.0),
            ),
        ),
        instructions="Cook.",
    )


def _day(offset: int) -> datetime.date:
    return THU + datetime.timedelta(days=offset)


_PLATE = split(
    "plate",
    Role("protein", frozenset({P}), missing=5, extra=3),
    Role("carb", frozenset({C}), missing=5, extra=3),
    Role("veg", frozenset({V}), missing=3, extra=1),
)
_ONE_DISH = single("one dish", Role("dish", frozenset({D}), missing=5, extra=3), 0.5)
_EAT_OUT = Archetype(
    "eat out", (Role("takeout", recipe_ids=frozenset({TAKEOUT})),), plannable=False
)
_LUNCHES = {LUNCH: (_PLATE, _ONE_DISH, _EAT_OUT)}

_RECIPES = [
    _recipe("chicken", P, servings=2),
    _recipe("beef", P, servings=2),
    _recipe("fish", P),
    _recipe("rice", C),
    _recipe("pasta", C),
    _recipe("buckwheat", C),
    _recipe("beans", V, servings=2),
    _recipe("broccoli", V, servings=2),
    _recipe("soup", D, servings=3),
]


def _problem(days: int = 1, **fields) -> Problem:
    slots = tuple(Slot(_day(d), LUNCH, THU) for d in range(days))
    return Problem(
        slots=fields.pop("slots", slots),
        history=fields.pop("history", ()),
        pins=fields.pop("pins", ()),
        batches=fields.pop("batches", ()),
        sessions=fields.pop("sessions", (THU,)),
        archetypes=fields.pop("archetypes", _LUNCHES),
        **fields,
    )


def _added(result: Plan, day: datetime.date = THU) -> list[str]:
    return sorted(p.recipe_id for p in result.placements if p.date == day)


def _category(recipe_id: str) -> RecipeCategory:
    return next(r.category for r in _RECIPES if r.id == recipe_id)


def test_an_empty_slot_gets_a_whole_archetype():
    result = plan(_RECIPES, _problem())
    meal = _added(result)
    assert sorted(_category(r) for r in meal) in ([C, V, P], [D])
    assert dict(result.points)["archetype fit"] <= 0.5  # at most a base cost


def test_a_half_filled_meal_is_completed_around_its_pin():
    pins = (Pin(THU, LUNCH, "fish", THU),)
    result = plan(_RECIPES, _problem(pins=pins, batches=(Batch(THU, "fish", 1, 1),)))
    added = _added(result)
    assert sorted(_category(r) for r in added) == [C, V]  # no second protein
    assert dict(result.points)["archetype fit"] == 0


def test_pins_that_break_the_archetype_cost_points_never_infeasibility():
    # Two proteins placed by hand: the slot pays an excess, the plan adds
    # a carb and a veg and nothing else.
    pins = (Pin(THU, LUNCH, "fish", THU), Pin(THU, LUNCH, "beef", THU))
    batches = (Batch(THU, "fish", 1, 1), Batch(THU, "beef", 1, 2, unassigned=1))
    result = plan(_RECIPES, _problem(pins=pins, batches=batches))
    assert sorted(_category(r) for r in _added(result)) == [C, V]
    assert dict(result.points)["archetype fit"] == 3  # one extra protein


def test_takeout_is_matched_and_left_alone():
    result = plan(_RECIPES, _problem(pins=(Pin(THU, LUNCH, TAKEOUT),)))
    assert _added(result) == []
    assert result.archetypes == ((THU, LUNCH, "eat out"),)


def test_eat_out_is_never_chosen_for_an_empty_slot():
    result = plan(_RECIPES, _problem())
    assert result.archetypes[0][2] != "eat out"


def test_unassigned_stock_is_used_before_cooking():
    # Monday's beef has a spare portion; eating it beats a new batch.
    monday = THU - datetime.timedelta(days=3)
    stock = Batch(monday, "beef", 1, 2, outside=1, unassigned=1, fixed=True)
    result = plan(_RECIPES, _problem(batches=(stock,)))
    beef = [p for p in result.placements if p.recipe_id == "beef"]
    assert [p.session for p in beef] == [monday]
    assert all(c.recipe_id != "beef" for c in result.cooks)


def test_stock_past_its_fridge_life_is_not_used():
    long_ago = THU - datetime.timedelta(days=10)
    stale = Batch(
        long_ago,
        "beef",
        1,
        2,
        unassigned=2,
        fixed=True,
        fridge_days=4,
        freezer_friendly=False,
    )
    result = plan(_RECIPES, _problem(batches=(stale,)))
    assert all(p.session != long_ago for p in result.placements)


def test_batches_are_used_up_and_leftovers_avoided():
    # Two lunches: a 2-portion protein and veg eaten on both days, a day
    # apart from nothing else; no leftovers.
    result = plan(_RECIPES, _problem(days=2, weights=Weights(next_day_repeat=0)))
    assert dict(result.points)["leftovers"] == 0


def test_a_recipe_twice_in_a_day_is_avoided():
    dinner = Mealtime.DINNER
    archetypes = {LUNCH: (_PLATE,), dinner: (_PLATE,)}
    slots = (Slot(THU, LUNCH, THU), Slot(THU, dinner, THU))
    result = plan(
        _RECIPES,
        _problem(slots=slots, archetypes=archetypes, weights=Weights(leftover=0)),
    )
    picked = [p.recipe_id for p in result.placements]
    assert len(picked) == len(set(picked))


def test_next_day_repeats_count_the_history_day():
    yesterday = THU - datetime.timedelta(days=1)
    history = (Slot(yesterday, LUNCH, yesterday),)
    pins = tuple(Pin(yesterday, LUNCH, r, None) for r in ("fish", "rice", "beans"))
    # Leftovers off: a 2-portion batch's spare would tie with a repeat.
    problem = _problem(history=history, pins=pins, weights=Weights(leftover=0))
    result = plan(_RECIPES, problem)
    assert not set(_added(result)) & {"fish", "rice", "beans"}
    assert all(p.date == THU for p in result.placements)  # history untouched


def test_a_cut_off_session_cooks_just_enough():
    result = plan(_RECIPES, _problem(truncated=frozenset({THU})))
    for cook in result.cooks:
        recipe = next(r for r in _RECIPES if r.id == cook.recipe_id)
        used = sum(1 for p in result.placements if p.recipe_id == cook.recipe_id)
        assert cook.batches == -(-used // int(recipe.servings))


def test_a_planned_session_keeps_its_batches_and_may_add():
    # Thursday already cooks one beef batch (2 portions) by hand.
    existing = Batch(THU, "beef", 1, 2, unassigned=2)
    result = plan(_RECIPES, _problem(days=3, batches=(existing,)))
    beef_cooks = [c for c in result.cooks if c.recipe_id == "beef"]
    assert all(c.batches >= 1 for c in beef_cooks)  # only ever additions


def test_a_dish_in_two_roles_of_one_archetype_is_rejected():
    both = Role("protein", frozenset({P}))
    archetypes = {LUNCH: (split("odd", both, Role("again", frozenset({P}))),)}
    with pytest.raises(ValueError, match="two roles"):
        plan(_RECIPES, _problem(archetypes=archetypes))


# -- scoring ----------------------------------------------------------------


def test_scoring_adds_nothing_and_itemizes_the_bill():
    from meal_prep.planner.solver import score

    pins = (Pin(THU, LUNCH, "fish", THU), Pin(THU, LUNCH, "rice", THU))
    batches = (Batch(THU, "fish", 1, 1), Batch(THU, "rice", 1, 1))
    result = score(_RECIPES, _problem(pins=pins, batches=batches))
    assert result.placements == () and result.cooks == ()
    assert result.archetypes == ((THU, LUNCH, "plate"),)
    (line,) = result.lines
    assert (line.term, line.reason, line.points) == (
        "archetype fit",
        "plate: veg missing",
        3,
    )
    assert (line.date, line.mealtime) == (THU, LUNCH)


def test_scoring_charges_repeats_and_leftovers_where_they_happen():
    from meal_prep.planner.solver import score

    friday = _day(1)
    slots = (Slot(THU, LUNCH, THU), Slot(friday, LUNCH, THU))
    pins = tuple(
        Pin(day, LUNCH, rid, THU)
        for day in (THU, friday)
        for rid in ("fish", "rice", "beans")
    )
    batches = (
        Batch(THU, "fish", 2, 1),
        Batch(THU, "rice", 3, 1, unassigned=1),  # one rice portion unused
        Batch(THU, "beans", 1, 2),
    )
    result = score(_RECIPES, _problem(slots=slots, pins=pins, batches=batches))
    by_term = dict(result.points)
    assert by_term["next-day repeats"] == 3  # fish, rice, beans on both days
    assert by_term["leftovers"] == 1
    leftover = next(line for line in result.lines if line.term == "leftovers")
    assert leftover.session == THU and "Recipe rice" in leftover.reason


def test_scoring_reports_broken_hard_rules_instead_of_failing():
    from meal_prep.planner.solver import score

    pins = (Pin(THU, LUNCH, "fish", THU), Pin(_day(1), LUNCH, "fish", THU))
    slots = (Slot(THU, LUNCH, THU), Slot(_day(1), LUNCH, THU))
    result = score(
        _RECIPES, _problem(slots=slots, pins=pins, batches=(Batch(THU, "fish", 1, 1),))
    )
    assert result.problems == (
        "fish of the 2026-11-05 session: 2 meals for 1 portions",
    )
