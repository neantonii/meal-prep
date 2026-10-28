"""Tests for the meal and diary enrichment services and frozen models."""

from __future__ import annotations

import pytest

from meal_prep.dtos.log import DiaryWeekDTO
from meal_prep.dtos.meal import MealDTO
from meal_prep.enums import Aisle, Mealtime, RecipeCategory, StorageType
from meal_prep.models.ingredient import MacrosInfo, Package
from meal_prep.models.meal import Meal
from meal_prep.models.recipe import Recipe, RecipeIngredient
from meal_prep.services.diary import freeze_entry
from meal_prep.services.logs import prepare_diary_week
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
                aisle=Aisle.PANTRY,
                storage=StorageType.AMBIENT,
                shelf_life_days=30,
                quantity=200.0,
                unit="g",
                grams=200.0,
                cost=cost * 2.0,
                macros=_macros(cal=cal * 2.0, protein=20.0),
                package=Package("Test 1 kg", 1.0, "kg", 1000.0),
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
# prepare_diary_week
# ---------------------------------------------------------------------------


def test_prepare_diary_week_uses_frozen_numbers_not_current_recipes(
    recipes: dict[str, Recipe],
):
    entry = freeze_entry(recipes["oatmeal"])
    diary = DiaryWeekDTO.model_validate(
        {
            "week": "2026-W42",
            "days": [
                {
                    "date": "2026-10-13",
                    "breakfast": [
                        entry,
                        entry.model_copy(
                            update={"id": freeze_entry(recipes["oatmeal"]).id}
                        ),
                    ],
                }
            ],
        }
    )
    # The recipe gets twice as expensive after logging; the diary must not notice.
    recipes["oatmeal"] = _recipe("oatmeal", cost=2.0, cal=999.0)
    week = prepare_diary_week(diary)
    assert week.total_cost == pytest.approx(2.0)
    assert week.total_macros.calories_kcal == pytest.approx(200.0)
    logged = week.days[0].meal(Mealtime.BREAKFAST)
    assert logged is not None
    assert logged.recipe_ids == ("oatmeal", "oatmeal")
    assert logged.entries[0].title == "Recipe oatmeal"
    assert logged.entries[0].entry_id == str(entry.id)


def test_prepare_diary_week_survives_deleted_recipe():
    gone = _recipe("gone", cost=3.0, cal=50.0)
    diary = DiaryWeekDTO.model_validate(
        {
            "week": "2026-W42",
            "days": [{"date": "2026-10-13", "dinner": [freeze_entry(gone)]}],
        }
    )
    week = prepare_diary_week(diary)
    assert week.total_cost == pytest.approx(3.0)
