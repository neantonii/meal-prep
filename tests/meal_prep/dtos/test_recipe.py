"""Tests for the recipe DTOs (``dtos/recipe.py``).

Happy paths plus our custom validation only. Pydantic's implicit field
constraints (``gt``, ``min_length``, enum coercion, aliases) are not re-tested.

Our custom validation in this module:
- ``RecipeFrontmatter.validate_id_format`` -> ``normalize_slug``
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from meal_prep.dtos.recipe import (
    Recipe,
    RecipeCookwareRef,
    RecipeFrontmatter,
    RecipeIngredientMention,
    RecipeIngredientRef,
    RecipeStorage,
    RecipeYield,
)


# ---------------------------------------------------------------------------
# RecipeYield — no custom validation (happy path only)
# ---------------------------------------------------------------------------


def test_recipe_yield_valid():
    y = RecipeYield.model_validate({"servings": 4, "cooked_g": 1600})
    assert y.servings == 4
    assert y.cooked_g == 1600


# ---------------------------------------------------------------------------
# RecipeStorage — no custom validation (happy path only)
# ---------------------------------------------------------------------------


def test_recipe_storage_valid():
    s = RecipeStorage.model_validate({"fridge_days": 4, "freezer_friendly": True})
    assert s.fridge_days == 4
    assert s.freezer_friendly is True


# ---------------------------------------------------------------------------
# RecipeFrontmatter — validate_id_format
# ---------------------------------------------------------------------------


def _frontmatter(**overrides):
    data = {
        "id": "grilled-chicken-rice",
        "title": "Grilled Chicken & Rice",
        "category": "modular_protein",
        "yield": {"servings": 4, "cooked_g": 1600},
        "storage": {"fridge_days": 4, "freezer_friendly": True},
    }
    data.update(overrides)
    return data


def test_frontmatter_valid():
    fm = RecipeFrontmatter.model_validate(_frontmatter())
    assert fm.id == "grilled-chicken-rice"
    assert fm.title == "Grilled Chicken & Rice"
    assert fm.category.value == "modular_protein"


def test_frontmatter_id_is_normalized():
    assert RecipeFrontmatter.model_validate(_frontmatter(id="  Grilled-Chicken-Rice  ")).id == (
        "grilled-chicken-rice"
    )


def test_frontmatter_id_invalid_slug_is_rejected():
    with pytest.raises(ValidationError, match="kebab-case slug"):
        RecipeFrontmatter.model_validate(_frontmatter(id="grilled_chicken"))


# ---------------------------------------------------------------------------
# RecipeIngredientRef / RecipeCookwareRef — no custom validation (happy path)
# ---------------------------------------------------------------------------


def test_recipe_ingredient_ref_valid():
    ref = RecipeIngredientRef.model_validate({"id": "boneless-chicken-breast", "quantity": 2, "unit": "piece"})
    assert ref.id == "boneless-chicken-breast"
    assert ref.quantity == 2
    assert ref.unit == "piece"


def test_recipe_ingredient_ref_empty_unit_means_count():
    ref = RecipeIngredientRef.model_validate({"id": "apple", "quantity": 1})
    assert ref.unit == ""


def test_recipe_ingredient_mention_valid():
    mention = RecipeIngredientMention.model_validate({"id": "boneless-chicken-breast"})
    assert mention.id == "boneless-chicken-breast"


def test_recipe_cookware_ref_valid():
    ref = RecipeCookwareRef.model_validate({"id": "air-fryer"})
    assert ref.id == "air-fryer"


# ---------------------------------------------------------------------------
# Recipe — no custom validation (happy path only)
# ---------------------------------------------------------------------------


def test_recipe_valid():
    recipe = Recipe.model_validate(
        {
            "id": "grilled-chicken-rice",
            "title": "Grilled Chicken & Rice",
            "category": "modular_protein",
            "yield": {"servings": 4, "cooked_g": 1600},
            "storage": {"fridge_days": 4, "freezer_friendly": True},
            "ingredients": [{"id": "boneless-chicken-breast", "quantity": 2, "unit": "piece"}],
            "cookware": [{"id": "air-fryer"}],
            "instructions": "Season and cook.",
        }
    )
    assert recipe.id == "grilled-chicken-rice"
    assert len(recipe.ingredients) == 1
    assert len(recipe.cookware) == 1
    assert recipe.instructions == "Season and cook."
    assert recipe.source_path is None
