"""Prep session DTOs — the shape of the gitignored session files
(``diary/sessions/<YYYY-MM-DD>.yaml``).

A prep session is a date plus the recipes prepared (or bought for) that day
(``docs/prep-sessions.md``). Sessions are not tied to diary weeks: diary
entries link to one by its id. Every item carries the numbers frozen when it
was added, ingredient lines included, so past sessions never change when
recipes, ingredients or prices do (#107). Parsing of the files lives in
``meal_prep.adapters.sessions``.

Compatibility rule (as for diary weeks): fields are only ever added, never
renamed or removed; a field added later must be optional.
"""

from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from meal_prep.dtos._normalize import normalize_slug
from meal_prep.enums import Aisle


class SessionPackageDTO(BaseModel):
    """The retail package an ingredient line is bought in, when added."""

    model_config = ConfigDict(extra="forbid")

    product: str = Field(..., min_length=1, description="Product title when added")
    amount: float = Field(
        ..., gt=0, description="Package size when added, in `unit` (e.g. 4)"
    )
    unit: str = Field(
        ..., min_length=1, description="Unit of `amount` (e.g. 'l', 'count')"
    )
    per_batch: float = Field(
        ..., ge=0, description="Packages one batch uses (a fraction is fine)"
    )


class SessionIngredientDTO(BaseModel):
    """One ingredient line of one batch, as it was when the item was added."""

    model_config = ConfigDict(extra="forbid")

    ingredient: str = Field(..., description="Ingredient id")
    name: str = Field(..., min_length=1, description="Ingredient name when added")
    grams: float = Field(..., ge=0, description="Grams used by one batch")
    cost: float = Field(..., ge=0, description="Cost of those grams, in CAD")
    # Added for the session's ingredient list; missing in older files.
    aisle: Aisle | None = Field(
        default=None, description="Supermarket aisle when added"
    )
    package: SessionPackageDTO | None = Field(
        default=None, description="Retail package when added"
    )

    @field_validator("ingredient")
    @classmethod
    def validate_ingredient_id(cls, v: str) -> str:
        return normalize_slug(v, field="Session ingredient id")


class SessionItemDTO(BaseModel):
    """One recipe of a session: how much is made, plus its frozen numbers."""

    model_config = ConfigDict(extra="forbid")

    recipe: str = Field(..., description="Recipe id")
    title: str = Field(..., min_length=1, description="Recipe title when added")
    batches: int = Field(..., ge=1, description="Times the recipe is made as written")
    ad_hoc: bool = Field(
        default=False,
        description="Deprecated and ignored; kept so existing session files "
        "load (to be replaced by a recipe property)",
    )
    servings: int = Field(..., ge=1, description="Portions per batch, when added")
    cost: float = Field(..., ge=0, description="Cost of one serving when added, in CAD")
    calories_kcal: float = Field(..., ge=0, description="Per serving, when added")
    protein_g: float = Field(..., ge=0, description="Per serving, when added")
    fat_g: float = Field(..., ge=0, description="Per serving, when added")
    carbs_g: float = Field(..., ge=0, description="Per serving, when added")
    fiber_g: float = Field(..., ge=0, description="Per serving, when added")
    saturated_fat_g: float = Field(..., ge=0, description="Per serving, when added")
    sugars_g: float = Field(..., ge=0, description="Per serving, when added")
    sodium_mg: float = Field(..., ge=0, description="Per serving, when added")
    potassium_mg: float = Field(..., ge=0, description="Per serving, when added")
    ingredients: list[SessionIngredientDTO] = Field(
        ..., description="Ingredient lines of one batch, when added"
    )

    @field_validator("recipe")
    @classmethod
    def validate_recipe_id(cls, v: str) -> str:
        return normalize_slug(v, field="Session recipe id")


class PrepSessionDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID = Field(..., description="Session id (UUID); never changes")
    date: datetime.date = Field(..., description="Day of the prep session")
    items: list[SessionItemDTO] = Field(
        ..., min_length=1, description="Recipes of the session, one item each"
    )

    @field_validator("items")
    @classmethod
    def validate_unique_recipes(cls, v: list[SessionItemDTO]) -> list[SessionItemDTO]:
        seen: set[str] = set()
        for item in v:
            if item.recipe in seen:
                raise ValueError(f"Recipe '{item.recipe}' is listed twice")
            seen.add(item.recipe)
        return v
