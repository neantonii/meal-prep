"""Prep session freezing and enrichment.

A session item's numbers — title, servings, per-serving cost and macros, and
one batch's ingredient lines — are frozen exactly once, when the item is
added (#107). Nothing here looks at current recipes afterwards.
"""

from __future__ import annotations

from meal_prep.dtos.session import (
    PrepSessionDTO,
    SessionIngredientDTO,
    SessionItemDTO,
)
from meal_prep.models.ingredient import MacrosInfo
from meal_prep.models.recipe import Recipe
from meal_prep.models.session import PrepSession, SessionIngredient, SessionItem


def whole_servings(recipe: Recipe) -> int:
    """``recipe``'s servings as a whole number of portions.

    Sessions count whole portions; a recipe yielding e.g. 2.5 servings can't
    be prepped until its yield is authored as a whole number.
    """
    if not recipe.servings.is_integer():
        raise ValueError(
            f"{recipe.title} yields {recipe.servings:g} servings; prep sessions "
            "need a whole number"
        )
    return int(recipe.servings)


def freeze_item(recipe: Recipe, batches: int = 1) -> SessionItemDTO:
    """A new session item carrying ``recipe``'s current numbers."""
    macros = recipe.per_serving_macros
    return SessionItemDTO(
        recipe=recipe.id,
        title=recipe.title,
        batches=batches,
        servings=whole_servings(recipe),
        cost=recipe.cost_per_portion,
        calories_kcal=macros.calories_kcal,
        protein_g=macros.protein_g,
        fat_g=macros.fat_g,
        carbs_g=macros.carbs_g,
        fiber_g=macros.fiber_g,
        saturated_fat_g=macros.saturated_fat_g,
        sugars_g=macros.sugars_g,
        sodium_mg=macros.sodium_mg,
        potassium_mg=macros.potassium_mg,
        ingredients=[
            SessionIngredientDTO(
                ingredient=line.id, name=line.name, grams=line.grams, cost=line.cost
            )
            for line in recipe.ingredients
        ],
    )


def _item(dto: SessionItemDTO) -> SessionItem:
    return SessionItem(
        recipe_id=dto.recipe,
        title=dto.title,
        batches=dto.batches,
        servings=dto.servings,
        cost=dto.cost,
        macros=MacrosInfo(
            calories_kcal=dto.calories_kcal,
            protein_g=dto.protein_g,
            fat_g=dto.fat_g,
            carbs_g=dto.carbs_g,
            fiber_g=dto.fiber_g,
            saturated_fat_g=dto.saturated_fat_g,
            sugars_g=dto.sugars_g,
            sodium_mg=dto.sodium_mg,
            potassium_mg=dto.potassium_mg,
        ),
        ingredients=tuple(
            SessionIngredient(
                ingredient_id=line.ingredient,
                name=line.name,
                grams=line.grams,
                cost=line.cost,
            )
            for line in dto.ingredients
        ),
    )


def prepare_session(dto: PrepSessionDTO) -> PrepSession:
    """Build a session from its frozen items (no recipe lookup)."""
    return PrepSession(
        session_id=str(dto.id),
        date=dto.date,
        items=tuple(_item(item) for item in dto.items),
    )
