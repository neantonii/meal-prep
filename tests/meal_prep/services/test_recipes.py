"""Tests for the recipe enrichment service (``services/recipes.py``).

Happy paths against the real catalog, plus the service's own validation errors
(unknown ingredient, unknown equipment, unregistered unit). Ingredient-level
gram reachability is already guaranteed by ingredient enrichment and is not
re-tested here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from meal_prep.dtos.recipe import Recipe as RecipeDTO
from meal_prep.dtos.recipe import RecipeIngredientRef
from meal_prep.library import MealPrepLibrary
from meal_prep.models.recipe import Recipe
from meal_prep.services.recipes import prepare_recipe

_REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def library() -> MealPrepLibrary:
    return MealPrepLibrary.load(
        data_dir=_REPO_ROOT / "data",
        recipes_dir=_REPO_ROOT / "recipes",
    )


@pytest.fixture(scope="module")
def chicken_recipe(library: MealPrepLibrary) -> RecipeDTO:
    return library.recipes["air-fried-chicken-breast"]


# ---------------------------------------------------------------------------
# happy paths
# ---------------------------------------------------------------------------


def test_prepare_recipe_resolves_everything(library, chicken_recipe):
    prepared = prepare_recipe(chicken_recipe, library.catalog, library.equipment)
    assert isinstance(prepared, Recipe)
    assert prepared.id == "air-fried-chicken-breast"
    assert prepared.servings == 4.0
    assert prepared.cooked_g == 660.0
    assert len(prepared.ingredients) == 6


def test_prepare_recipe_equipment_names_are_resolved(library, chicken_recipe):
    prepared = prepare_recipe(chicken_recipe, library.catalog, library.equipment)
    assert prepared.equipment == ("Air Fryer", "Meat Thermometer")


def test_prepare_recipe_computes_cost_and_macros(library, chicken_recipe):
    prepared = prepare_recipe(chicken_recipe, library.catalog, library.equipment)
    assert prepared.total_cost > 0.0
    assert prepared.cost_per_portion == prepared.total_cost / prepared.servings
    assert prepared.batch_macros.calories_kcal > 0.0
    assert prepared.per_serving_macros.calories_kcal > 0.0


def test_prepare_recipe_merges_duplicate_ingredient_references(library):
    # Oil appears once in this recipe; reference it twice to force a merge.
    recipe = library.recipes["air-fried-chicken-breast"].model_copy(
        update={
            "ingredients": [
                RecipeIngredientRef(id="olive-oil", quantity=1, unit="tbsp"),
                RecipeIngredientRef(id="olive-oil", quantity=0.5, unit="tbsp"),
            ],
            "mentions": [],
        }
    )
    prepared = prepare_recipe(recipe, library.catalog, library.equipment)
    assert [i.id for i in prepared.ingredients] == ["olive-oil"]
    ingredient = prepared.ingredients[0]
    assert ingredient.grams == pytest.approx(
        library.catalog["olive-oil"].convert(1.5, "tbsp", "g")
    )
    # Display uses the first-authored unit, summed into it.
    assert ingredient.unit == "tbsp"
    assert ingredient.quantity == pytest.approx(1.5)
    assert ingredient.repeated is True


def test_prepare_recipe_merges_mixed_units_into_first_unit(library):
    # 1 tsp + 1 tbsp of the same ingredient -> expressed in the first unit (tsp).
    recipe = library.recipes["air-fried-chicken-breast"].model_copy(
        update={
            "ingredients": [
                RecipeIngredientRef(id="olive-oil", quantity=1, unit="tsp"),
                RecipeIngredientRef(id="olive-oil", quantity=1, unit="tbsp"),
            ],
            "mentions": [],
        }
    )
    prepared = prepare_recipe(recipe, library.catalog, library.equipment)
    ingredient = prepared.ingredients[0]
    assert ingredient.unit == "tsp"
    assert ingredient.quantity == pytest.approx(4.0)  # 1 tsp + (1 tbsp = 3 tsp)
    # Canonical grams stay correct regardless of display unit.
    assert ingredient.grams == pytest.approx(
        library.catalog["olive-oil"].convert(4.0, "tsp", "g")
    )
    assert ingredient.repeated is True


# ---------------------------------------------------------------------------
# validation errors
# ---------------------------------------------------------------------------


def test_prepare_recipe_rejects_unknown_ingredient(library, chicken_recipe):
    recipe = chicken_recipe.model_copy(
        update={"ingredients": [RecipeIngredientRef(id="not-an-ingredient", quantity=1, unit="g")]}
    )
    with pytest.raises(ValueError, match="unknown ingredient 'not-an-ingredient'"):
        prepare_recipe(recipe, library.catalog, library.equipment)


def test_prepare_recipe_rejects_unknown_cookware(library, chicken_recipe):
    from meal_prep.dtos.recipe import RecipeCookwareRef

    recipe = chicken_recipe.model_copy(
        update={"cookware": [RecipeCookwareRef(id="skilllet")]}
    )
    with pytest.raises(ValueError, match="unknown cookware 'skilllet'"):
        prepare_recipe(recipe, library.catalog, library.equipment)


def test_prepare_recipe_resolves_cookware_alias_to_canonical_name(library, chicken_recipe):
    from meal_prep.dtos.recipe import RecipeCookwareRef

    recipe = chicken_recipe.model_copy(
        update={"cookware": [RecipeCookwareRef(id="pan")]}
    )
    prepared = prepare_recipe(recipe, library.catalog, library.equipment)
    # "pan" is an alias of the "skillet" item, not a canonical id.
    assert prepared.equipment == ("Large Non-Stick Skillet",)
    assert prepared.cookware_by_token["pan"] == "Large Non-Stick Skillet"


def test_prepare_recipe_resolves_cookware_canonical_id(library, chicken_recipe):
    from meal_prep.dtos.recipe import RecipeCookwareRef

    recipe = chicken_recipe.model_copy(
        update={"cookware": [RecipeCookwareRef(id="air-fryer")]}
    )
    prepared = prepare_recipe(recipe, library.catalog, library.equipment)
    assert prepared.equipment == ("Air Fryer",)
    assert prepared.cookware_by_token["air-fryer"] == "Air Fryer"


def test_prepare_recipe_rejects_unregistered_unit(library, chicken_recipe):
    recipe = chicken_recipe.model_copy(
        update={"ingredients": [RecipeIngredientRef(id="olive-oil", quantity=1, unit="furlong")]}
    )
    with pytest.raises(ValueError, match="unknown unit 'furlong'"):
        prepare_recipe(recipe, library.catalog, library.equipment)


def test_prepare_recipe_rejects_mention_without_declaration(library, chicken_recipe):
    from meal_prep.dtos.recipe import RecipeIngredientMention

    recipe = chicken_recipe.model_copy(
        update={
            "ingredients": [RecipeIngredientRef(id="olive-oil", quantity=1, unit="tbsp")],
            "mentions": [RecipeIngredientMention(id="kosher-salt")],
        }
    )
    with pytest.raises(ValueError, match="mentions ingredient 'kosher-salt'"):
        prepare_recipe(recipe, library.catalog, library.equipment)


def test_prepare_recipe_allows_mention_with_declaration(library, chicken_recipe):
    from meal_prep.dtos.recipe import RecipeIngredientMention

    recipe = chicken_recipe.model_copy(
        update={
            "ingredients": [RecipeIngredientRef(id="olive-oil", quantity=1, unit="tbsp")],
            "mentions": [RecipeIngredientMention(id="olive-oil")],
        }
    )
    prepared = prepare_recipe(recipe, library.catalog, library.equipment)
    assert [i.id for i in prepared.ingredients] == ["olive-oil"]
