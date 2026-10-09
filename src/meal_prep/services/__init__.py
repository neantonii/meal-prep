"""Business-logic services.

Services resolve collaborators (the units registry, the conversion graph) that
models must not depend on, and construct the frozen enriched values in
``meal_prep.models``. Only services touch DTOs; downstream consumers see only
the enriched values.
"""

from meal_prep.services.heuristics import check_ingredient
from meal_prep.services.ingredients import prepare_catalog, prepare_ingredient
from meal_prep.services.logs import prepare_log_week
from meal_prep.services.meals import prepare_meal
from meal_prep.services.recipes import prepare_recipe

__all__ = [
    "check_ingredient",
    "prepare_catalog",
    "prepare_ingredient",
    "prepare_log_week",
    "prepare_meal",
    "prepare_recipe",
]
