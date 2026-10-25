"""Library assembly — load and enrich all authored data in one call.

``load_library`` is the composition root between the loading machinery
(adapters → DTOs → services) and everything that consumes the domain. It reads
the authored files, enriches ingredients, recipes and meals, and returns one
frozen ``Library`` of models. Consumers never see DTOs or call services.

All locations are explicit: nothing is resolved against the working directory.
"""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType

from meal_prep.adapters.equipment import load_equipment
from meal_prep.adapters.ingredients import load_all_ingredients
from meal_prep.adapters.meals import load_all_meals
from meal_prep.adapters.recipes import load_all_recipes
from meal_prep.adapters.units import load_units
from meal_prep.models.library import Library
from meal_prep.models.meal import Meal
from meal_prep.services.ingredients import prepare_catalog
from meal_prep.services.meals import prepare_meal
from meal_prep.services.recipes import prepare_recipe


def load_library(
    data_dir: Path | str,
    recipes_dir: Path | str,
    meals_dir: Path | str | None = None,
) -> Library:
    """Load, validate and enrich the whole workspace into a frozen ``Library``.

    Args:
        data_dir: Holds ``units.yaml``, ``equipment.yaml`` and ``ingredients/``.
        recipes_dir: Holds ``<category>/<slug>.cook`` recipe files.
        meals_dir: Holds authored meal YAML files; ``None`` means no meals.

    Raises on the first invalid file or failed cross-reference.
    """
    data_path = Path(data_dir)
    units = load_units(data_path / "units.yaml")
    equipment = load_equipment(data_path / "equipment.yaml")
    ingredients = prepare_catalog(
        load_all_ingredients(data_path / "ingredients"), units
    )

    recipes = {
        recipe_id: prepare_recipe(dto, ingredients, equipment)
        for recipe_id, dto in load_all_recipes(Path(recipes_dir)).items()
    }

    meals: dict[str, Meal] = {}
    if meals_dir is not None:
        meals = {
            meal_id: prepare_meal(dto, recipes)
            for meal_id, dto in load_all_meals(Path(meals_dir)).items()
        }

    return Library(
        ingredients=MappingProxyType(ingredients),
        recipes=MappingProxyType(recipes),
        meals=MappingProxyType(meals),
    )
