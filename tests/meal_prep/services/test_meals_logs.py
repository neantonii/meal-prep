"""Tests for the meal/log enrichment services and frozen models."""

from __future__ import annotations

from datetime import date

import pytest

from meal_prep.dtos.log import LogDayDTO, LoggedSlotDTO, LogWeekDTO
from meal_prep.dtos.meal import MealDTO
from meal_prep.enums import Mealtime, RecipeCategory, StorageType
from meal_prep.models.ingredient import MacrosInfo
from meal_prep.models.log import LogDay, LoggedSlot, LogWeek
from meal_prep.models.meal import Meal
from meal_prep.models.recipe import Recipe, RecipeIngredient
from meal_prep.services.logs import prepare_log_week
from meal_prep.services.meals import prepare_meal


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


def _recipe(recipe_id: str, *, cost: float, cal: float) -> Recipe:
    return Recipe(
        id=recipe_id,
        title=f"Recipe {recipe_id}",
        category=RecipeCategory.BREAKFAST,
        servings=2.0,
        cooked_g=400.0,
        fridge_days=4,
        freezer_friendly=True,
        equipment=(),
        cookware_by_token={},
        ingredients=(
            RecipeIngredient(
                id="a",
                name="A",
                step_name="a",
                aisle_name="Pantry",
                aisle_order=6,
                storage=StorageType.AMBIENT,
                shelf_life_days=30,
                quantity=200.0,
                unit="g",
                grams=200.0,
                cost=cost * 2.0,
                macros=_macros(cal=cal * 2.0, protein=20.0),
            ),
        ),
        instructions="Cook.",
    )


@pytest.fixture
def recipes() -> dict[str, Recipe]:
    return {
        "oatmeal": _recipe("oatmeal", cost=1.0, cal=100.0),
        "coffee": _recipe("coffee", cost=0.5, cal=10.0),
    }


# ---------------------------------------------------------------------------
# prepare_meal
# ---------------------------------------------------------------------------


def test_prepare_meal_sums_one_serving_per_entry(recipes: dict[str, Recipe]):
    meal = prepare_meal(
        MealDTO.model_validate(
            {
                "id": "morning",
                "title": "Morning",
                "recipes": ["oatmeal", "coffee", "oatmeal"],
            }
        ),
        recipes,
    )
    assert isinstance(meal, Meal)
    assert meal.recipe_ids == ("oatmeal", "coffee", "oatmeal")
    assert meal.total_cost == pytest.approx(1.0 + 0.5 + 1.0)
    assert meal.total_macros.calories_kcal == pytest.approx(210.0)
    assert meal.total_cooked_g == pytest.approx(600.0)


def test_prepare_meal_rejects_unknown_recipe(recipes: dict[str, Recipe]):
    with pytest.raises(ValueError, match="unknown recipe"):
        prepare_meal(
            MealDTO.model_validate({"id": "bad", "title": "Bad", "recipes": ["nope"]}),
            recipes,
        )


# ---------------------------------------------------------------------------
# prepare_log_week
# ---------------------------------------------------------------------------


def test_prepare_log_week_aggregates(recipes: dict[str, Recipe]):
    week = prepare_log_week(
        LogWeekDTO.model_validate(
            {
                "week": "2026-W42",
                "days": [
                    {
                        "date": "2026-10-13",
                        "slots": [
                            {
                                "mealtime": "breakfast",
                                "recipes": ["oatmeal", "coffee"],
                            },
                            {"mealtime": "snacks", "recipes": ["oatmeal"]},
                        ],
                    },
                    {
                        "date": "2026-10-14",
                        "slots": [{"mealtime": "lunch", "recipes": ["coffee"]}],
                    },
                ],
            }
        ),
        recipes,
    )
    assert isinstance(week, LogWeek)
    assert week.week == "2026-W42"
    assert len(week.days) == 2
    assert week.total_cost == pytest.approx(1.0 + 0.5 + 1.0 + 0.5)
    assert week.total_macros.calories_kcal == pytest.approx(100 + 10 + 100 + 10)

    day = week.days[0]
    assert isinstance(day, LogDay)
    assert day.date == date(2026, 10, 13)
    assert day.slot(Mealtime.BREAKFAST) is not None
    assert day.slot(Mealtime.LUNCH) is None
    assert day.cost == pytest.approx(2.5)

    slot = day.slot(Mealtime.BREAKFAST)
    assert isinstance(slot, LoggedSlot)
    assert slot.recipe_ids == ("oatmeal", "coffee")
    assert slot.macros.protein_g == pytest.approx(20.0)


def test_prepare_log_week_rejects_unknown_recipe(recipes: dict[str, Recipe]):
    with pytest.raises(ValueError, match="unknown recipe"):
        prepare_log_week(
            LogWeekDTO(
                week="2026-W42",
                days=[
                    LogDayDTO(
                        date=date(2026, 10, 13),
                        slots=[
                            LoggedSlotDTO(mealtime=Mealtime.BREAKFAST, recipes=["nope"])
                        ],
                    )
                ],
            ),
            recipes,
        )
