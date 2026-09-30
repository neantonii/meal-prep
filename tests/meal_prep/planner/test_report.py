"""Tests for the week-plan HTML report (``meal_prep/planner/report.py``)."""

from __future__ import annotations

from meal_prep.enums import RecipeCategory
from meal_prep.models.ingredient import MacrosInfo
from meal_prep.planner.plan import DailyPlannedMeal, PlannedMeal, WeekPlan
from meal_prep.planner.report import render_week_plan


def _meal(recipe_id: str = "rice") -> PlannedMeal:
    return PlannedMeal(
        recipe_id=recipe_id,
        title="Boiled Rice",
        cost=0.24,
        macros=MacrosInfo(
            calories_kcal=211.0,
            protein_g=5.3,
            fat_g=0.0,
            carbs_g=47.5,
            fiber_g=0.0,
            saturated_fat_g=0.0,
            sugars_g=0.0,
            sodium_mg=0.0,
            potassium_mg=0.0,
        ),
    )


def _plan() -> WeekPlan:
    return WeekPlan(
        days=tuple(
            DailyPlannedMeal(
                day=f"Day {idx}",
                breakfast=_meal(),
                lunch=_meal(),
                dinner=_meal(),
            )
            for idx in range(7)
        ),
    )


def test_report_is_standalone_html_with_totals():
    page = render_week_plan(_plan())
    assert page.startswith("<!DOCTYPE html>")
    assert "Weekly Meal Plan" in page
    assert "$5.04" in page
    assert page.count('class="day-card"') == 7
    assert "Breakfast" in page and "Lunch" in page and "Dinner" in page


def test_report_links_recipe_cards_when_lookup_given():
    from meal_prep.models.recipe import Recipe

    recipe = Recipe(
        id="rice",
        title="Boiled Rice",
        category=RecipeCategory.MODULAR_CARB,
        servings=1.0,
        cooked_g=200.0,
        fridge_days=4,
        freezer_friendly=True,
        equipment=(),
        cookware_by_token={},
        ingredients=(),
        instructions="Cook.",
    )
    page = render_week_plan(_plan(), recipes={"rice": recipe})
    assert "recipe_cards/modular_carb/rice.html" in page
