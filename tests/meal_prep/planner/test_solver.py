"""Tests for the planner's solver (``meal_prep/planner/solver.py``).

All recipes are hand-built fakes, so the best plan is known exactly.
"""

from __future__ import annotations

import datetime

import pytest

from meal_prep.enums import Aisle, Mealtime, RecipeCategory, StorageType
from meal_prep.models.ingredient import MacrosInfo, Package
from meal_prep.models.recipe import Recipe, RecipeIngredient
from meal_prep.planner.plan import MealSlot, MealTemplate, Option, Role, Weights
from meal_prep.planner.solver import NoPlanError, plan

P = RecipeCategory.MODULAR_PROTEIN
C = RecipeCategory.MODULAR_CARB
D = RecipeCategory.ONE_DISH
THU = datetime.date(2026, 11, 5)


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


def _lunches(days: int, session: datetime.date = THU) -> list[MealSlot]:
    return [MealSlot(_day(d), Mealtime.LUNCH, session) for d in range(days)]


_PLATE = Option(
    "plate", (Role("protein", frozenset({P})), Role("carb", frozenset({C})))
)
_ONE_DISH = Option("one dish", (Role("one dish", frozenset({D})),))
_LUNCH = {Mealtime.LUNCH: MealTemplate(options=(_PLATE, _ONE_DISH))}


def _by_day(result) -> dict[datetime.date, set[str]]:
    days: dict[datetime.date, set[str]] = {}
    for pick in result.picks:
        days.setdefault(pick.slot.date, set()).add(pick.recipe_id)
    return days


def test_every_slot_follows_one_option_of_its_template():
    recipes = [_recipe("chicken"), _recipe("rice", C), _recipe("soup", D)]
    result = plan(recipes, _lunches(3), _LUNCH)
    for meal in _by_day(result).values():
        assert meal in ({"chicken", "rice"}, {"soup"})


def test_fixed_sets_are_eaten_whole_and_extras_are_optional():
    breakfast = {
        Mealtime.BREAKFAST: MealTemplate(
            options=(
                Option(
                    "oats",
                    (
                        Role("oats", recipe_ids=frozenset({"oats"})),
                        Role("coffee", recipe_ids=frozenset({"coffee"})),
                    ),
                ),
            ),
            extras=Role("snack", recipe_ids=frozenset({"apple"})),
        )
    }
    recipes = [
        _recipe("oats", RecipeCategory.BREAKFAST),
        _recipe("coffee", RecipeCategory.BREAKFAST),
        _recipe("apple", RecipeCategory.SNACKS),
        _recipe("eggs", RecipeCategory.BREAKFAST),  # fits nothing
    ]
    slots = [MealSlot(THU, Mealtime.BREAKFAST, THU)]
    meal = _by_day(plan(recipes, slots, breakfast))[THU]
    assert {"oats", "coffee"} <= meal <= {"oats", "coffee", "apple"}


def test_a_recipe_is_eaten_once_a_day_counting_fixed_meals():
    recipes = [
        _recipe("chicken"),
        _recipe("beef"),
        _recipe("rice", C),
        _recipe("pasta", C),
        _recipe("buckwheat", C),
    ]
    dinner = {Mealtime.DINNER: MealTemplate(options=(_PLATE,))}
    slots = [MealSlot(THU, Mealtime.LUNCH, THU), MealSlot(THU, Mealtime.DINNER, THU)]
    result = plan(recipes, slots, {**_LUNCH, **dinner}, eaten={THU: {"rice"}})
    picked = [p.recipe_id for p in result.picks]
    assert len(picked) == len(set(picked))  # nothing twice on Thursday
    assert "rice" not in picked  # already eaten that day


def test_batches_cover_the_meals_and_leftovers_are_avoided():
    # A 2-portion protein eaten on two days beats two 1-portion batches of
    # anything with a portion left over.
    recipes = [_recipe("chicken", servings=2), _recipe("rice", C)]
    result = plan(recipes, _lunches(2), {Mealtime.LUNCH: MealTemplate((_PLATE,))})
    batches = {b.recipe_id: b for b in result.batches}
    assert (batches["chicken"].batches, batches["chicken"].used) == (1, 2)
    assert dict(result.points)["leftovers"] == 0


def test_leftovers_count_points():
    # Three lunches of a 2-portion recipe: 2 batches, one portion left over.
    recipes = [_recipe("chicken", servings=2), _recipe("rice", C)]
    template = {Mealtime.LUNCH: MealTemplate((_PLATE,))}
    result = plan(recipes, _lunches(3), template, weights=Weights(next_day_repeat=0))
    (chicken,) = [b for b in result.batches if b.recipe_id == "chicken"]
    assert (chicken.batches, chicken.used, chicken.leftover) == (2, 3, 1)
    assert dict(result.points)["leftovers"] == 1


def test_truncated_sessions_cook_just_enough_and_pay_nothing():
    recipes = [_recipe("chicken", servings=2), _recipe("rice", C)]
    template = {Mealtime.LUNCH: MealTemplate((_PLATE,))}
    result = plan(
        recipes,
        _lunches(1),
        template,
        truncated={THU},
    )
    (chicken,) = [b for b in result.batches if b.recipe_id == "chicken"]
    assert (chicken.batches, chicken.leftover) == (1, 1)
    assert dict(result.points)["leftovers"] == 0


def test_next_day_repeats_are_avoided_but_a_day_between_is_free():
    recipes = [
        _recipe("chicken"),
        _recipe("beef"),
        _recipe("rice", C),
        _recipe("pasta", C),
    ]
    template = {Mealtime.LUNCH: MealTemplate((_PLATE,))}
    result = plan(recipes, _lunches(4), template, weights=Weights(leftover=0))
    days = _by_day(result)
    for d in range(3):
        assert not days[_day(d)] & days[_day(d + 1)]
    assert dict(result.points)["next-day repeats"] == 0


def test_repeats_count_against_the_day_before_the_plan():
    recipes = [
        _recipe("chicken"),
        _recipe("beef"),
        _recipe("rice", C),
        _recipe("pasta", C),
    ]
    template = {Mealtime.LUNCH: MealTemplate((_PLATE,))}
    yesterday = THU - datetime.timedelta(days=1)
    result = plan(
        recipes, _lunches(1), template, eaten={yesterday: {"chicken", "rice"}}
    )
    assert _by_day(result)[THU] == {"beef", "pasta"}


def test_unavoidable_repeats_are_charged():
    recipes = [_recipe("chicken"), _recipe("rice", C)]
    template = {Mealtime.LUNCH: MealTemplate((_PLATE,))}
    result = plan(recipes, _lunches(3), template, weights=Weights(leftover=0))
    # chicken and rice on Thu-Fri and Fri-Sat: 4 repeats.
    assert dict(result.points)["next-day repeats"] == 4


def test_an_option_a_missing_recipe_breaks_is_left_out():
    recipes = [_recipe("soup", D)]  # no protein or carb: only the one dish fits
    result = plan(recipes, _lunches(1), _LUNCH)
    assert _by_day(result)[THU] == {"soup"}


def test_no_fitting_recipe_is_an_error():
    with pytest.raises(NoPlanError):
        plan(
            [_recipe("rice", C)], _lunches(1), {Mealtime.LUNCH: MealTemplate((_PLATE,))}
        )


def test_a_recipe_may_be_shared_by_two_options():
    # Coffee comes with either breakfast.
    def fixed(name: str, *ids: str) -> Option:
        return Option(name, tuple(Role(i, recipe_ids=frozenset({i})) for i in ids))

    template = {
        Mealtime.BREAKFAST: MealTemplate(
            (fixed("oats", "oats", "coffee"), fixed("eggs", "eggs", "coffee"))
        )
    }
    recipes = [_recipe(i, RecipeCategory.BREAKFAST) for i in ("oats", "eggs", "coffee")]
    slots = [MealSlot(_day(d), Mealtime.BREAKFAST, THU) for d in range(2)]
    days = _by_day(plan(recipes, slots, template))
    assert sorted(map(sorted, days.values())) == [
        ["coffee", "eggs"],
        ["coffee", "oats"],
    ]


def test_a_recipe_in_two_roles_of_one_option_is_rejected():
    both = Role("p", frozenset({P}))
    template = {Mealtime.LUNCH: MealTemplate((Option("x", (both, both)),))}
    with pytest.raises(ValueError, match="more than one role"):
        plan([_recipe("chicken")], _lunches(1), template)
