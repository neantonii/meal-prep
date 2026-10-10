"""Data access adapters — the only code that reads files or parses external formats.

Each adapter translates between an on-disk format (YAML, Cooklang) and the DTOs
in ``meal_prep.dtos``. DTOs never construct themselves from files; they are
always built by an adapter here. Adapters import DTOs, never the reverse.
"""

from meal_prep.adapters.aisles import load_aisles
from meal_prep.adapters.equipment import load_equipment
from meal_prep.adapters.ingredients import load_all_ingredients, load_ingredients_file
from meal_prep.adapters.logs import load_all_logs, load_log_file
from meal_prep.adapters.meals import load_all_meals, load_meal_file
from meal_prep.adapters.recipes import (
    load_all_recipes,
    load_recipe_file,
    parse_cooklang_body,
    split_recipe_file,
)
from meal_prep.adapters.units import load_units

__all__ = [
    "load_aisles",
    "load_all_ingredients",
    "load_all_logs",
    "load_all_meals",
    "load_all_recipes",
    "load_equipment",
    "load_ingredients_file",
    "load_log_file",
    "load_meal_file",
    "load_recipe_file",
    "load_units",
    "parse_cooklang_body",
    "split_recipe_file",
]
