"""Recipe model.

Holds the schema for a parsed recipe and the (soon-to-be-relocated) computation
helpers. Parsing of .cook files lives in ``meal_prep.adapters.recipes``.
"""

from pathlib import Path
import re
from pydantic import BaseModel, ConfigDict, Field, field_validator
from meal_prep.models.enums import RecipeCategory
from meal_prep.models.ingredient import Ingredient, MacrosInfo
from meal_prep.models.units import UnitsRegistry
from meal_prep.models.equipment import EquipmentRegistry


class RecipeYield(BaseModel):
    servings: float = Field(..., gt=0, description="Number of portions produced by the batch")
    cooked_g: float = Field(..., gt=0, description="Total finished cooked batch weight in grams")


class RecipeStorage(BaseModel):
    fridge_days: int = Field(..., gt=0, description="Maximum safe refrigerated shelf life in days")
    freezer_friendly: bool = Field(..., description="Whether the cooked batch can be frozen")


class RecipeFrontmatter(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Unique alphanumeric slug with hyphens matching file stem")
    title: str = Field(..., min_length=1, description="Human-readable recipe title")
    category: RecipeCategory = Field(..., description="Recipe category enum")
    yield_info: RecipeYield = Field(..., alias="yield", description="Portion count and cooked batch weight")
    storage_info: RecipeStorage = Field(..., alias="storage", description="Storage specifications")
    equipment: list[str] = Field(..., min_length=1, description="List of equipment IDs required")

    @field_validator("id")
    @classmethod
    def validate_id_format(cls, v: str) -> str:
        clean = v.strip().lower()
        if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", clean):
            raise ValueError(f"Recipe id '{v}' must be alphanumeric with hyphens (kebab-case)")
        return clean


class RecipeIngredientRef(BaseModel):
    id: str = Field(..., description="Ingredient identifier matching catalog id")
    quantity: float = Field(..., gt=0, description="Quantity used in recipe")
    unit: str = Field(..., min_length=1, description="Measurement unit (must convert to grams)")


class RecipeCookwareRef(BaseModel):
    id: str = Field(..., description="Equipment identifier or canonical name")


class RecipeTimerRef(BaseModel):
    name: str = Field(..., description="Timer description or name")
    duration: float = Field(..., gt=0, description="Timer duration value")
    unit: str = Field(..., min_length=1, description="Time unit (s, min, hr)")


class Recipe(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    title: str
    category: RecipeCategory
    yield_info: RecipeYield = Field(..., alias="yield")
    storage_info: RecipeStorage = Field(..., alias="storage")
    equipment: list[str]
    ingredients: list[RecipeIngredientRef]
    cookware: list[RecipeCookwareRef]
    timers: list[RecipeTimerRef]
    instructions: str
    source_path: Path | None = None

    @property
    def portion_cooked_weight_g(self) -> float:
        """Portion weight in grams per serving."""
        return round(self.yield_info.cooked_g / self.yield_info.servings, 1)

    def compute_raw_batch_weight_g(
        self,
        catalog: dict[str, Ingredient],
        units: UnitsRegistry,
    ) -> float:
        """Compute total raw un-cooked batch weight in grams."""
        total_g = 0.0
        for item in self.ingredients:
            if item.id not in catalog:
                raise ValueError(f"Ingredient '{item.id}' in recipe '{self.id}' not found in ingredients catalog")
            ing = catalog[item.id]
            grams = ing.convert(item.quantity, item.unit, "g", units=units)
            total_g += grams
        return round(total_g, 1)

    def compute_cooking_loss_percent(
        self,
        catalog: dict[str, Ingredient],
        units: UnitsRegistry,
    ) -> float:
        """Compute cooking/moisture yield loss percentage."""
        raw_g = self.compute_raw_batch_weight_g(catalog, units)
        if raw_g <= 0:
            return 0.0
        loss = (1.0 - (self.yield_info.cooked_g / raw_g)) * 100.0
        return round(loss, 1)

    def compute_macros(
        self,
        catalog: dict[str, Ingredient],
        units: UnitsRegistry,
    ) -> tuple[MacrosInfo, MacrosInfo]:
        """Compute total batch macros and per-serving macros.
        
        Returns:
            (batch_macros, serving_macros)
        """
        batch_macros_dict: dict[str, float] = {
            "calories_kcal": 0.0,
            "protein_g": 0.0,
            "fat_g": 0.0,
            "saturated_fat_g": 0.0,
            "carbs_g": 0.0,
            "fiber_g": 0.0,
            "sugars_g": 0.0,
            "sodium_mg": 0.0,
            "potassium_mg": 0.0,
        }

        for item in self.ingredients:
            if item.id not in catalog:
                raise ValueError(f"Ingredient '{item.id}' in recipe '{self.id}' not found in ingredients catalog")
            ing = catalog[item.id]
            grams = ing.convert(item.quantity, item.unit, "g", units=units)
            factor = grams / 100.0

            m = ing.macros_per_100g
            for key in batch_macros_dict:
                val = getattr(m, key, 0.0) or 0.0
                batch_macros_dict[key] += val * factor

        # Round batch macros
        for key in batch_macros_dict:
            batch_macros_dict[key] = round(batch_macros_dict[key], 1)

        batch_macros = MacrosInfo.model_validate(batch_macros_dict)

        # Compute per-serving macros
        servings = self.yield_info.servings
        serving_macros_dict = {
            key: round(batch_macros_dict[key] / servings, 1)
            for key in batch_macros_dict
        }
        serving_macros = MacrosInfo.model_validate(serving_macros_dict)

        return batch_macros, serving_macros

    def compute_cost(
        self,
        catalog: dict[str, Ingredient],
        units: UnitsRegistry,
    ) -> tuple[float, float]:
        """Compute estimated batch retail cost and cost per serving in CAD.
        
        Returns:
            (batch_cost, serving_cost)
        """
        total_cost = 0.0
        # TODO(services/KI-01): `compute_*` on Recipe is a duplicate of the
        # calculator service and is slated for deletion; the lazy import below is
        # a temporary, flagged models -> services edge.
        from meal_prep.services.pricing import price_per_100g
        for item in self.ingredients:
            if item.id not in catalog:
                raise ValueError(f"Ingredient '{item.id}' in recipe '{self.id}' not found in ingredients catalog")
            ing = catalog[item.id]
            grams = ing.convert(item.quantity, item.unit, "g", units=units)
            item_cost = (grams / 100.0) * price_per_100g(ing, units)
            total_cost += item_cost

        batch_cost = round(total_cost, 2)
        serving_cost = round(batch_cost / self.yield_info.servings, 2)
        return batch_cost, serving_cost

    def compute_safe_fridge_days(self, catalog: dict[str, Ingredient]) -> int:
        """Compute safe fridge storage window constrained by ingredient shelf life."""
        safe_days = self.storage_info.fridge_days
        for item in self.ingredients:
            if item.id in catalog:
                safe_days = min(safe_days, catalog[item.id].shelf_life_days)
        return safe_days
