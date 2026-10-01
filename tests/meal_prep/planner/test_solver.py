"""Tests for the week-plan solver (``meal_prep/planner/solver.py``).

All recipes are hand-built fakes; the cheapest assignment is known exactly.
"""

from __future__ import annotations

import pytest

from meal_prep.enums import RecipeCategory, StorageType
from meal_prep.models.ingredient import MacrosInfo
from meal_prep.models.recipe import Recipe, RecipeIngredient
from meal_prep.planner.plan import WeekPlan
from meal_prep.planner.solver import plan_week


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
    *,
    cost: float,
    category: RecipeCategory = RecipeCategory.MODULAR_PROTEIN,
    servings: float = 1.0,
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
                aisle_name="Meat",
                aisle_order=3,
                storage=StorageType.REFRIGERATED,
                shelf_life_days=3,
                quantity=200.0,
                unit="g",
                grams=200.0,
                cost=cost,
                macros=_macros(),
            ),
        ),
        instructions="Cook.",
    )


def test_picks_cheapest_meal_every_meal():
    plan = plan_week(
        [
            _recipe("cheap", cost=1.0),
            _recipe("also-cheap", cost=1.0),
            _recipe("pricey", cost=9.0),
            _recipe("morning", cost=2.0, category=RecipeCategory.BREAKFAST),
        ]
    )
    assert isinstance(plan, WeekPlan)
    assert len(plan.days) == 7
    for day in plan.days:
        assert day.breakfast.recipe_id == "morning"
        assert {day.lunch.recipe_id, day.dinner.recipe_id} == {
            "cheap",
            "also-cheap",
        }
    # servings=1 and no repeats within a day: 7 uses each in 7 batches.
    assert [(batch.recipe_id, batch.batches) for batch in plan.prep] == [
        ("also-cheap", 7),
        ("cheap", 7),
        ("morning", 7),
    ]
    assert plan.total_cost == 7 * 1.0 + 7 * 1.0 + 7 * 2.0


def test_breakfast_comes_from_breakfast_category():
    plan = plan_week(
        [
            _recipe("oats", cost=5.0, category=RecipeCategory.BREAKFAST),
            _recipe("eggs", cost=1.0, category=RecipeCategory.BREAKFAST),
            _recipe("stew", cost=0.5),
            _recipe("soup", cost=0.6),
        ]
    )
    for day in plan.days:
        assert day.breakfast.recipe_id == "eggs"
        assert {day.lunch.recipe_id, day.dinner.recipe_id} == {"stew", "soup"}


def test_no_recipe_repeats_within_a_day():
    plan = plan_week(
        [
            _recipe("morning", cost=1.0, category=RecipeCategory.BREAKFAST),
            _recipe("second-morning", cost=1.0, category=RecipeCategory.BREAKFAST),
            _recipe("stew", cost=0.5),
            _recipe("soup", cost=0.6),
            _recipe("pasta", cost=0.7),
        ]
    )
    for day in plan.days:
        served = (day.breakfast.recipe_id, day.lunch.recipe_id, day.dinner.recipe_id)
        assert len(set(served)) == 3


def test_single_recipe_per_slot_solves():
    plan = plan_week(
        [
            _recipe("morning", cost=2.5, category=RecipeCategory.BREAKFAST),
            _recipe("midday", cost=2.5),
            _recipe("evening", cost=2.5),
        ]
    )
    assert isinstance(plan, WeekPlan)
    assert [(batch.recipe_id, batch.batches) for batch in plan.prep] == [
        ("evening", 7),
        ("midday", 7),
        ("morning", 7),
    ]


def test_big_batch_needs_fewer_batches():
    plan = plan_week(
        [
            _recipe("morning", cost=1.0, category=RecipeCategory.BREAKFAST),
            _recipe("tray", cost=6.0, servings=4.0),
            _recipe("pot", cost=5.0, servings=2.0),
            _recipe("single", cost=4.0, servings=1.0),
        ]
    )
    # Breakfasts: morning every day, 7 batches. Lunch/dinner (14 uses, no
    # same-day repeats so tray covers at most 7): 2 trays cover 7 uses
    # ($12) + 3 pots cover 6 ($15) + 1 single ($4) beats a 4th pot ($20).
    assert [(batch.recipe_id, batch.batches) for batch in plan.prep] == [
        ("morning", 7),
        ("pot", 3),
        ("single", 1),
        ("tray", 2),
    ]
    assert plan.total_cost == 7 * 1.0 + 3 * 5.0 + 1 * 4.0 + 2 * 6.0


def test_leftover_is_charged_at_full_batch_cost():
    plan = plan_week(
        [
            _recipe("morning", cost=1.0, category=RecipeCategory.BREAKFAST),
            _recipe("tray", cost=6.0, servings=4.0),
            _recipe("single", cost=2.0, servings=1.0),
            _recipe("other", cost=2.0, servings=1.0),
        ]
    )
    # 14 lunch/dinner uses: 2 trays cover 7 uses ($12, 1 leftover) + 7
    # singles cover 7 ($14) beats 14 singles ($28). Leftover is tolerated
    # but charged: the tray line costs the full 2 batches.
    by_id = {batch.recipe_id: batch for batch in plan.prep}
    assert by_id["tray"].batches == 2
    assert by_id["tray"].portions_used == 7
    assert by_id["tray"].leftover == 1
    assert by_id["tray"].cost == 12.0
    assert plan.total_cost == 7 * 1.0 + 12.0 + 7 * 2.0


def test_rejects_empty_recipes():
    with pytest.raises(ValueError, match="at least one recipe"):
        plan_week([])


def test_rejects_missing_breakfast_recipes():
    with pytest.raises(ValueError, match="at least one breakfast recipe"):
        plan_week([_recipe("stew", cost=1.0)])


def test_many_recipes_solve():
    recipes = [_recipe(f"meal-{idx}", cost=float(idx + 1)) for idx in range(10)]
    recipes.append(_recipe("morning", cost=0.5, category=RecipeCategory.BREAKFAST))
    plan = plan_week(recipes)
    assert isinstance(plan, WeekPlan)
