"""Recipe model.

Holds the schema for a parsed recipe: the YAML frontmatter and the Cooklang
body references. Parsing of .cook files lives in ``meal_prep.adapters.recipes``.
"""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from meal_prep.dtos._normalize import normalize_slug
from meal_prep.enums import RecipeCategory


class RecipeYield(BaseModel):
    servings: float = Field(
        ..., gt=0, description="Number of portions produced by the batch"
    )
    cooked_g: float = Field(
        ..., gt=0, description="Total finished cooked batch weight in grams"
    )


class RecipeStorage(BaseModel):
    fridge_days: int = Field(
        ..., gt=0, description="Maximum safe refrigerated shelf life in days"
    )
    freezer_friendly: bool = Field(
        ..., description="Whether the cooked batch can be frozen"
    )


class RecipeFrontmatter(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(
        ..., description="Unique alphanumeric slug with hyphens matching file stem"
    )
    title: str = Field(..., min_length=1, description="Human-readable recipe title")
    category: RecipeCategory = Field(..., description="Recipe category enum")
    yield_info: RecipeYield = Field(
        ..., alias="yield", description="Portion count and cooked batch weight"
    )
    storage_info: RecipeStorage = Field(
        ..., alias="storage", description="Storage specifications"
    )

    @field_validator("id")
    @classmethod
    def validate_id_format(cls, v: str) -> str:
        return normalize_slug(v, field="Recipe id")


class RecipeIngredientRef(BaseModel):
    id: str = Field(..., description="Ingredient identifier matching catalog id")
    quantity: float = Field(..., gt=0, description="Quantity used in recipe")
    unit: str = Field(
        "",
        description="Measurement unit; empty string means a count (resolved to the "
        "reserved 'count' node during enrichment).",
    )


class RecipeIngredientMention(BaseModel):
    """An amount-less ingredient reference (``@name`` or ``@name{}``).

    Carries only an id. A mention contributes nothing to quantity and must be
    backed by a declaration elsewhere in the recipe; the recipe service enforces
    that invariant.
    """

    id: str = Field(..., description="Ingredient identifier matching catalog id")


class RecipeCookwareRef(BaseModel):
    id: str = Field(..., description="Equipment identifier or canonical name")


class RecipeDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    title: str
    category: RecipeCategory
    yield_info: RecipeYield = Field(..., alias="yield")
    storage_info: RecipeStorage = Field(..., alias="storage")
    ingredients: list[RecipeIngredientRef]
    mentions: list[RecipeIngredientMention] = Field(
        default_factory=list, description="Amount-less ingredient references"
    )
    cookware: list[RecipeCookwareRef]
    instructions: str
    source_path: Path | None = None
