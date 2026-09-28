"""Data transfer objects — deserialization and shape validation only.

These models mirror the authored YAML/Cooklang files and carry raw values.
They perform shape validation only; no enrichment, lookup, conversion, or
cross-validation logic lives here. The conversion graph lives in
``meal_prep.engines``; enriched values and registries are built by services.
"""

from meal_prep.dtos.aisle import Aisle
from meal_prep.dtos.equipment import EquipmentItem
from meal_prep.enums import StorageType, RecipeCategory
from meal_prep.dtos.ingredient import (
    Ingredient,
    ReferenceInfo,
    MacrosInfo,
    UnitConversion,
)
from meal_prep.dtos.recipe import (
    Recipe,
    RecipeFrontmatter,
    RecipeYield,
    RecipeStorage,
    RecipeIngredientRef,
    RecipeIngredientMention,
    RecipeCookwareRef,
)
from meal_prep.dtos.units import ConversionStep, DimensionGroup, UnitsFileSchema

__all__ = [
    "Aisle",
    "EquipmentItem",
    "StorageType",
    "RecipeCategory",
    "Ingredient",
    "ReferenceInfo",
    "MacrosInfo",
    "UnitConversion",
    "Recipe",
    "RecipeFrontmatter",
    "RecipeYield",
    "RecipeStorage",
    "RecipeIngredientRef",
    "RecipeIngredientMention",
    "RecipeCookwareRef",
    "ConversionStep",
    "DimensionGroup",
    "UnitsFileSchema",
]

