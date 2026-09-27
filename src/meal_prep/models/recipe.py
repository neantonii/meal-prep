"""Recipe model.

Holds the schema for a parsed recipe: the YAML frontmatter and the Cooklang
body references. Parsing of .cook files lives in ``meal_prep.adapters.recipes``.
"""

from pathlib import Path
import re
from pydantic import BaseModel, ConfigDict, Field, field_validator
from meal_prep.models.enums import RecipeCategory


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
