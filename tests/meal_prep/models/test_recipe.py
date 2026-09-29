"""Tests for the enriched recipe model (``models/recipe.py``).

Covers the pure aggregate computations of ``Recipe`` and the frozen value
semantics of both dataclasses. The service (``prepare_recipe``) is tested
separately in ``tests/meal_prep/services/test_recipes.py``.
"""

from __future__ import annotations

from meal_prep.enums import RecipeCategory, StorageType
from meal_prep.models.ingredient import MacrosInfo
from meal_prep.models.recipe import Recipe, RecipeIngredient


def _macros(*, cal=100.0, protein=10.0, fat=5.0, carbs=20.0, fiber=1.0) -> MacrosInfo:
    return MacrosInfo(
        calories_kcal=cal,
        protein_g=protein,
        fat_g=fat,
        carbs_g=carbs,
        fiber_g=fiber,
        saturated_fat_g=0.0,
        sugars_g=0.0,
        sodium_mg=0.0,
        potassium_mg=0.0,
    )


def _recipe() -> Recipe:
    return Recipe(
        id="test-recipe",
        title="Test Recipe",
        category=RecipeCategory.MODULAR_PROTEIN,
        servings=2.0,
        cooked_g=330.0,
        fridge_days=4,
        freezer_friendly=True,
        equipment=("Air Fryer",),
        cookware_by_token={"air-fryer": "Air Fryer"},
        ingredients=(
            RecipeIngredient(
                id="a",
                name="A",
                step_name="A",
                aisle_name="Meat",
                aisle_order=3,
                storage=StorageType.REFRIGERATED,
                shelf_life_days=3,
                quantity=200.0,
                unit="g",
                grams=200.0,
                cost=4.0,
                macros=_macros(),
            ),
            RecipeIngredient(
                id="b",
                name="B",
                step_name="B",
                aisle_name="Pantry",
                aisle_order=6,
                storage=StorageType.AMBIENT,
                shelf_life_days=365,
                quantity=100.0,
                unit="g",
                grams=100.0,
                cost=1.0,
                macros=_macros(cal=50.0),
            ),
        ),
        instructions="Cook.",
    )


# ---------------------------------------------------------------------------
# aggregate computations
# ---------------------------------------------------------------------------


def test_total_cost_sums_ingredient_costs():
    assert _recipe().total_cost == 5.0


def test_cost_per_portion_divides_by_servings():
    assert _recipe().cost_per_portion == 2.5


def test_portion_cooked_g_divides_by_servings():
    assert _recipe().portion_cooked_g == 165.0


def test_batch_macros_sums_every_ingredient():
    macros = _recipe().batch_macros
    assert macros.calories_kcal == 150.0  # 100 + 50
    assert macros.protein_g == 20.0  # 10 + 10
    assert macros.fat_g == 10.0  # 5 + 5


def test_per_serving_macros_divides_batch_by_servings():
    macros = _recipe().per_serving_macros
    assert macros.calories_kcal == 75.0
    assert macros.protein_g == 10.0


def test_empty_ingredients_yield_zero_aggregates():
    recipe = Recipe(
        id="empty",
        title="Empty",
        category=RecipeCategory.BREAKFAST,
        servings=1.0,
        cooked_g=0.0,
        fridge_days=1,
        freezer_friendly=False,
        equipment=(),
        cookware_by_token={},
        ingredients=(),
        instructions="",
    )
    assert recipe.total_cost == 0.0
    assert recipe.batch_macros == MacrosInfo.zero()


def test_source_path_defaults_to_none():
    assert _recipe().source_path is None


# ---------------------------------------------------------------------------
# frozen value semantics
# ---------------------------------------------------------------------------


def test_recipe_ingredient_is_frozen():
    ing = RecipeIngredient(
        id="a",
        name="A",
        step_name="A",
        aisle_name="Meat",
        aisle_order=3,
        storage=StorageType.REFRIGERATED,
        shelf_life_days=3,
        quantity=1.0,
        unit="g",
        grams=1.0,
        cost=1.0,
        macros=_macros(),
    )
    try:
        ing.grams = 5.0  # type: ignore[misc]
    except Exception as exc:  # noqa: BLE001
        assert type(exc).__name__ == "FrozenInstanceError"
    else:
        raise AssertionError("RecipeIngredient is not frozen")
