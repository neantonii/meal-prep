"""Shared domain vocabulary — closed sets of legal values used to constrain fields.

These are dependency-free leaves (stdlib ``enum`` only). They are neither DTOs
(decoded authored documents) nor enriched values, and they never change across
the DTO/enrichment boundary. For now they may be imported from anywhere.
"""

from enum import Enum


class StorageType(str, Enum):
    AMBIENT = "ambient"
    REFRIGERATED = "refrigerated"
    FROZEN = "frozen"

    @property
    def display_name(self) -> str:
        return {
            StorageType.AMBIENT: "Pantry (Ambient)",
            StorageType.REFRIGERATED: "Refrigerated (Chilled)",
            StorageType.FROZEN: "Frozen",
        }[self]


class RecipeCategory(str, Enum):
    MODULAR_PROTEIN = "modular_protein"
    MODULAR_CARB = "modular_carb"
    MODULAR_COOKED_VEG = "modular_cooked_veg"
    FRESH_SALAD_VEG = "fresh_salad_veg"
    BREAKFAST = "breakfast"

    @property
    def display_name(self) -> str:
        return {
            RecipeCategory.MODULAR_PROTEIN: "Modular Protein",
            RecipeCategory.MODULAR_CARB: "Modular Side (Carbs)",
            RecipeCategory.MODULAR_COOKED_VEG: "Modular Side (Cooked Veg)",
            RecipeCategory.FRESH_SALAD_VEG: "Fresh Vegetables & Salads",
            RecipeCategory.BREAKFAST: "Breakfast",
        }[self]

    @property
    def description(self) -> str:
        return {
            RecipeCategory.MODULAR_PROTEIN: "High-protein core batch prep (chicken, beef, fish, turkey)",
            RecipeCategory.MODULAR_CARB: "Starchy sides (rice, buckwheat, potatoes, pasta)",
            RecipeCategory.MODULAR_COOKED_VEG: "Cooked vegetable sides (green beans, cauliflower, corn & peas)",
            RecipeCategory.FRESH_SALAD_VEG: "Raw crunchy salads and fresh veg (vitaminka, cucumber-tomato)",
            RecipeCategory.BREAKFAST: "Quick-cook morning meals (oatmeal, eggs & toast)",
        }[self]

import os  # probe: unused import, ruff F401 will fail the check
