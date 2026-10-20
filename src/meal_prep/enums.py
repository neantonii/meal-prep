"""Shared domain vocabulary — closed sets of legal values used to constrain fields.

These are dependency-free leaves (stdlib ``enum`` only). They are neither DTOs
(decoded authored documents) nor enriched values, and they never change across
the DTO/enrichment boundary. For now they may be imported from anywhere.

The members are bare values with no presentation strings: human-facing labels
live with their consumers (``meal_prep.renderer`` for storage and category
strings, ``meal_prep.logbook.report`` for mealtime headers), where exhaustive
``match`` statements keep them in sync with the members.
"""

from enum import Enum


class StorageType(str, Enum):
    AMBIENT = "ambient"
    REFRIGERATED = "refrigerated"
    FROZEN = "frozen"


class Mealtime(str, Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACKS = "snacks"


class RecipeCategory(str, Enum):
    MODULAR_PROTEIN = "modular_protein"
    MODULAR_CARB = "modular_carb"
    MODULAR_COOKED_VEG = "modular_cooked_veg"
    FRESH_SALAD_VEG = "fresh_salad_veg"
    BREAKFAST = "breakfast"


class Aisle(str, Enum):
    """Supermarket aisles in walking order (definition order is the order)."""

    PRODUCE = "produce"
    MEAT = "meat"
    SEAFOOD = "seafood"
    DAIRY = "dairy"
    PANTRY = "pantry"
    SPICES = "spices"
