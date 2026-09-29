"""Data transfer objects — deserialization and shape validation only.

These models mirror the authored YAML/Cooklang files and carry raw values.
They perform shape validation only; no enrichment, lookup, conversion, or
cross-validation logic lives here. The conversion graph lives in
``meal_prep.engines``; enriched values and registries are built by services.
"""

from meal_prep.dtos.aisle import Aisle
from meal_prep.dtos.equipment import EquipmentItem
from meal_prep.dtos.ingredient import (
    IngredientDTO,
    MacrosInfoDTO,
    ReferenceInfo,
    UnitConversion,
)
from meal_prep.dtos.recipe import (
    RecipeCookwareRef,
    RecipeDTO,
    RecipeFrontmatter,
    RecipeIngredientMention,
    RecipeIngredientRef,
    RecipeStorage,
    RecipeYield,
)
from meal_prep.dtos.units import ConversionStep, DimensionGroup, UnitsFileSchema
from meal_prep.enums import RecipeCategory, StorageType

__all__ = [
    "Aisle",
    "ConversionStep",
    "DimensionGroup",
    "EquipmentItem",
    "IngredientDTO",
    "MacrosInfoDTO",
    "RecipeCategory",
    "RecipeCookwareRef",
    "RecipeDTO",
    "RecipeFrontmatter",
    "RecipeIngredientMention",
    "RecipeIngredientRef",
    "RecipeStorage",
    "RecipeYield",
    "ReferenceInfo",
    "StorageType",
    "UnitConversion",
    "UnitsFileSchema",
]
