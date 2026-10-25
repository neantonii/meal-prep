"""Enriched domain values — frozen, fully-resolved public building blocks.

These are distinct from the authored DTOs in ``meal_prep.dtos``. An enriched
value is computed once by a service (which resolves collaborators such as the
units registry and the conversion graph) and is thereafter immutable and
self-sufficient. Only services construct these; downstream consumers only read
them.
"""

from meal_prep.models.ingredient import Ingredient, MacrosInfo
from meal_prep.models.library import Library
from meal_prep.models.log import LogDay, LoggedMeal, LogWeek
from meal_prep.models.meal import Meal
from meal_prep.models.recipe import Recipe, RecipeIngredient

__all__ = [
    "Ingredient",
    "Library",
    "LogDay",
    "LogWeek",
    "LoggedMeal",
    "MacrosInfo",
    "Meal",
    "Recipe",
    "RecipeIngredient",
]
