"""Tests for the root-level recipe card renderer (``renderer.py``).

Covers the presentation concern this module owns: which name is shown where.
The instruction-step badges use the ingredient's ``step_name`` (prose-friendly)
while the tooltip title and the shopping checklist keep the full ``name``.
"""

from __future__ import annotations

import renderer
from meal_prep.enums import RecipeCategory
from meal_prep.models.ingredient import MacrosInfo
from meal_prep.models.recipe import Recipe, RecipeIngredient


def _macros() -> MacrosInfo:
    return MacrosInfo(
        calories_kcal=100.0,
        protein_g=10.0,
        fat_g=5.0,
        carbs_g=20.0,
        fiber_g=1.0,
        saturated_fat_g=0.0,
        sugars_g=0.0,
        sodium_mg=0.0,
        potassium_mg=0.0,
    )


def _recipe() -> Recipe:
    return Recipe(
        id="test",
        title="Test",
        category=RecipeCategory.MODULAR_PROTEIN,
        servings=1.0,
        cooked_g=200.0,
        fridge_days=3,
        freezer_friendly=False,
        equipment=(),
        equipment_by_id={},
        ingredients=(
            RecipeIngredient(
                id="boneless-chicken-breast",
                name="Boneless, Skinless Chicken Breast",
                step_name="chicken breasts",
                quantity=4.0,
                unit="piece",
                grams=950.0,
                cost=22.61,
                macros=_macros(),
            ),
        ),
        instructions="Trim any excess fat from @boneless-chicken-breast{4%piece}.",
    )


def test_step_badge_uses_step_name():
    html = renderer.render_recipe_card(_recipe())
    # Visible badge text uses the prose-friendly short noun.
    assert "4 piece chicken breasts" in html
    # Full canonical name is not shown inline in the step.
    assert "Boneless, Skinless Chicken Breast" in html  # present only as tooltip
    assert 'title="Ingredient: Boneless, Skinless Chicken Breast">4 piece chicken breasts' in html


def test_checklist_uses_full_name():
    html = renderer.render_recipe_card(_recipe())
    assert '<span class="ing-name">Boneless, Skinless Chicken Breast</span>' in html


def test_step_name_falls_back_to_full_name():
    recipe = _recipe()
    # Rebuild with step_name == full name (the service default when unset).
    from dataclasses import replace

    ing = replace(recipe.ingredients[0], step_name="Boneless, Skinless Chicken Breast")
    recipe = replace(recipe, ingredients=(ing,))
    html = renderer.render_recipe_card(recipe)
    assert "4 piece Boneless, Skinless Chicken Breast" in html
