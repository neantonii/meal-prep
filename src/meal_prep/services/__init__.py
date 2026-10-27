"""Business-logic services.

Services resolve collaborators (the units registry, the conversion graph) that
models must not depend on, and construct the frozen enriched values in
``meal_prep.models``. Only services touch DTOs; downstream consumers see only
the enriched values.
"""

from meal_prep.services.diary import (
    EntryNotFoundError,
    add_entry,
    freeze_entry,
    move_entry,
    remove_entry,
)
from meal_prep.services.heuristics import check_ingredient
from meal_prep.services.ingredients import prepare_catalog, prepare_ingredient
from meal_prep.services.logs import prepare_diary_week
from meal_prep.services.meals import prepare_meal
from meal_prep.services.recipes import prepare_recipe

__all__ = [
    "EntryNotFoundError",
    "add_entry",
    "check_ingredient",
    "freeze_entry",
    "move_entry",
    "prepare_catalog",
    "prepare_diary_week",
    "prepare_ingredient",
    "prepare_meal",
    "prepare_recipe",
    "remove_entry",
]
