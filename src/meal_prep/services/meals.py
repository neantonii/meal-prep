"""Meal enrichment service.

Turns an authored meal DTO into the frozen, fully-resolved ``Meal`` value by
resolving each recipe id against prepared recipes. Entries keep authored order
and duplicates are preserved — every entry counts as one serving, so listing
an id twice doubles its contribution to cost and macros.

Meal validation is deliberately trivial here: recipe enrichment already
guarantees sane cost/macros, so this service only checks that every referenced
recipe exists.
"""

from __future__ import annotations

from collections.abc import Mapping

from meal_prep.dtos.meal import MealDTO
from meal_prep.models.meal import Meal
from meal_prep.models.recipe import Recipe


def prepare_meal(meal: MealDTO, recipes: Mapping[str, Recipe]) -> Meal:
    """Resolve one authored meal into its frozen enriched value."""
    resolved: list[Recipe] = []
    for recipe_id in meal.recipes:
        recipe = recipes.get(recipe_id)
        if recipe is None:
            raise ValueError(
                f"Meal '{meal.id}' references unknown recipe '{recipe_id}'."
            )
        resolved.append(recipe)
    return Meal(
        id=meal.id,
        title=meal.title,
        recipes=tuple(resolved),
        source_path=meal.source_path,
    )
