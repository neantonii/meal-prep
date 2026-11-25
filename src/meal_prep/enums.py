"""Shared domain vocabulary — closed sets of legal values used to constrain fields.

These are dependency-free leaves (stdlib ``enum`` only). They are neither DTOs
(decoded authored documents) nor enriched values, and they never change across
the DTO/enrichment boundary. For now they may be imported from anywhere.

The members are bare values with no presentation strings: human-facing labels
live with their consumers (``meal_prep.renderer`` for storage and category
strings, ``meal_prep.logbook.report`` for mealtime headers), where exhaustive
``match`` statements keep them in sync with the members.
"""

from enum import StrEnum


class StorageType(StrEnum):
    AMBIENT = "ambient"
    REFRIGERATED = "refrigerated"
    FROZEN = "frozen"


class Mealtime(StrEnum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACKS = "snacks"


class RecipeCategory(StrEnum):
    MODULAR_PROTEIN = "modular_protein"
    MODULAR_CARB = "modular_carb"
    MODULAR_COOKED_VEG = "modular_cooked_veg"
    FRESH_SALAD_VEG = "fresh_salad_veg"
    ONE_DISH = "one_dish"
    BREAKFAST = "breakfast"
    SNACKS = "snacks"


class MealRole(StrEnum):
    """The part of a meal a recipe plays, where its category is too coarse
    to say (breakfast and snack recipes). The planner's archetypes name
    these, never recipe ids (``docs/planner.md``, "Archetypes")."""

    OVERNIGHT_OATS = "overnight_oats"
    BOILED_EGGS = "boiled_eggs"
    HOT_BREAKFAST = "hot_breakfast"
    COFFEE = "coffee"
    FRUIT = "fruit"
    SNACK_BOWL = "snack_bowl"
    FRUIT_BOWL = "fruit_bowl"


class Aisle(StrEnum):
    """Supermarket aisles in walking order (definition order is the order).

    Frozen session lines store these values (``docs/prep-sessions.md``), so a
    value is never renamed or removed: new aisles are only added (reordering
    is fine). A retired aisle stays a member, unused by current ingredients.
    """

    PRODUCE = "produce"
    MEAT = "meat"
    SEAFOOD = "seafood"
    DAIRY = "dairy"
    PANTRY = "pantry"
    SPICES = "spices"
