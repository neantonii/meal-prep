"""Prep session freezing and enrichment.

A session item's numbers — title, servings, per-serving cost and macros, and
one batch's ingredient lines — are frozen exactly once, when the item is
added (#107). Nothing here looks at current recipes afterwards; the meals of
its portions copy the item's numbers (``portion_entry``).
"""

from __future__ import annotations

import uuid

from meal_prep.dtos.log import RecipeEntryDTO
from meal_prep.dtos.session import (
    PrepSessionDTO,
    SessionIngredientDTO,
    SessionItemDTO,
    SessionPackageDTO,
)
from meal_prep.models.ingredient import MacrosInfo
from meal_prep.models.recipe import Recipe
from meal_prep.models.session import (
    PackageSize,
    PrepSession,
    SessionIngredient,
    SessionItem,
)


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
        fridge_days=recipe.fridge_days,
        freezer_friendly=recipe.freezer_friendly,
        ingredients=[
            SessionIngredientDTO(
                ingredient=line.id,
                name=line.name,
                grams=line.grams,
                cost=line.cost,
                aisle=line.aisle,
                package=SessionPackageDTO(
                    product=line.package.product,
                    amount=line.package.amount,
                    unit=line.package.unit,
                    per_batch=line.grams / line.package.weight_g,
                ),
            )
            for line in recipe.ingredients
        ],
    )


def portion_entry(item: SessionItemDTO, session: uuid.UUID) -> RecipeEntryDTO:
    """A new meal for one portion of ``item``, linked to ``session``: the
    numbers of the batch as it is cooked, not of today's recipe."""
    return RecipeEntryDTO(
        id=uuid.uuid4(),
        session=session,
        recipe=item.recipe,
        title=item.title,
        cost=item.cost,
        calories_kcal=item.calories_kcal,
        protein_g=item.protein_g,
        fat_g=item.fat_g,
        carbs_g=item.carbs_g,
        fiber_g=item.fiber_g,
        saturated_fat_g=item.saturated_fat_g,
        sugars_g=item.sugars_g,
        sodium_mg=item.sodium_mg,
        potassium_mg=item.potassium_mg,
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
                aisle=line.aisle,
                package=(
                    None
                    if line.package is None
                    else PackageSize(
                        product=line.package.product,
                        amount=line.package.amount,
                        unit=line.package.unit,
                    )
                ),
                packages=None if line.package is None else line.package.per_batch,
            )
            for line in dto.ingredients
        ),
        fridge_days=dto.fridge_days,
        freezer_friendly=dto.freezer_friendly,
    )


def prepare_session(dto: PrepSessionDTO) -> PrepSession:
    """Build a session from its frozen items (no recipe lookup)."""
    return PrepSession(
        session_id=str(dto.id),
        date=dto.date,
        items=tuple(_item(item) for item in dto.items),
    )
