"""Data access adapters — the only code that reads files or parses external formats.

Each adapter translates between an on-disk format (YAML, Cooklang) and the Pydantic
models in ``meal_prep.models``. Models never construct themselves from files; they
are always built by an adapter here. Adapters import models, never the reverse.
"""

from meal_prep.adapters.units import get_default_units, load_units
from meal_prep.adapters.equipment import load_equipment
from meal_prep.adapters.aisles import load_aisles
from meal_prep.adapters.ingredients import load_all_ingredients, load_ingredients_file
from meal_prep.adapters.recipes import (
    load_all_recipes,
    load_recipe_file,
    parse_cooklang_body,
    split_recipe_file,
)

__all__ = [
    "get_default_units",
    "load_units",
    "load_equipment",
    "load_aisles",
    "load_all_ingredients",
    "load_ingredients_file",
    "load_all_recipes",
    "load_recipe_file",
    "parse_cooklang_body",
    "split_recipe_file",
]
