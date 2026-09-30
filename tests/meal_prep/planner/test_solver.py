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


def _recipe(recipe_id: str, *, cost: float) -> Recipe:
    return Recipe(
        id=recipe_id,
        title=f"Recipe {recipe_id}",
        category=RecipeCategory.MODULAR_PROTEIN,
        servings=1.0,
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
    plan = plan_week([_recipe("cheap", cost=1.0), _recipe("pricey", cost=9.0)])
    assert isinstance(plan, WeekPlan)
    assert len(plan.days) == 7
    for day in plan.days:
        assert day.breakfast.recipe_id == "cheap"
        assert day.lunch.recipe_id == "cheap"
        assert day.dinner.recipe_id == "cheap"
    assert plan.total_cost == 21.0


def test_single_recipe_solves():
    plan = plan_week([_recipe("only", cost=2.5)])
    assert isinstance(plan, WeekPlan)


def test_rejects_empty_recipes():
    with pytest.raises(ValueError, match="at least one recipe"):
        plan_week([])


def test_many_recipes_solve():
    recipes = [_recipe(f"meal-{idx}", cost=float(idx + 1)) for idx in range(10)]
    plan = plan_week(recipes)
    assert isinstance(plan, WeekPlan)
