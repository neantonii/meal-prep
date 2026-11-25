"""Archetypes DTO: the shape of ``data/archetypes.yaml``.

What a meal looks like, per mealtime (``docs/planner.md``, "Archetypes"):
each archetype is a set of roles, each role a pool of dishes (recipe
categories and named recipes) with a target count and the points for
each dish short of or over it. Groupings that categories can't express
(which breakfasts go together) live here, never on recipes. Parsing of
the file lives in ``meal_prep.adapters.archetypes``; cross-checks against
the recipes in ``meal_prep.services.archetypes``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from meal_prep.dtos._normalize import normalize_slug
from meal_prep.enums import RecipeCategory


class RoleDTO(BaseModel):
    """One part of a meal: a pool of dishes and how many it wants."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, description="Shown in plan explanations")
    categories: list[RecipeCategory] = Field(
        default_factory=list, description="Every recipe of these categories"
    )
    recipes: list[str] = Field(
        default_factory=list, description="Named recipe ids, on top of categories"
    )
    takeout: bool = Field(
        default=False, description="Takes a takeout meal (eating out)"
    )
    count: tuple[int, int] = Field(
        default=(1, 1), description="[fewest, most] dishes the role wants"
    )
    missing: float = Field(..., ge=0, description="Points per dish short of fewest")
    extra: float = Field(..., ge=0, description="Points per dish over most")

    @field_validator("recipes")
    @classmethod
    def validate_ids(cls, v: list[str]) -> list[str]:
        return [normalize_slug(i, field="Archetype recipe id") for i in v]

    @model_validator(mode="after")
    def check_pool_and_count(self) -> RoleDTO:
        if not (self.categories or self.recipes or self.takeout):
            raise ValueError(f"role '{self.name}' has an empty pool")
        low, high = self.count
        if not 0 <= low <= high:
            raise ValueError(f"role '{self.name}': count must be 0 <= fewest <= most")
        return self


class ArchetypeDTO(BaseModel):
    """One meal shape: its roles and what choosing it costs."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, description="Shown in plan explanations")
    roles: list[RoleDTO] = Field(
        ..., min_length=1, description="The parts of the meal; a dish fits one"
    )
    base_cost: float = Field(
        default=0.0, ge=0, description="Points for choosing this archetype at all"
    )
    unknown: float = Field(
        default=1.0, ge=0, description="Points per dish no role takes"
    )
    plannable: bool = Field(
        default=True,
        description="The planner may choose it for an empty slot (false: it "
        "only matches meals already there, like eating out)",
    )


class ArchetypesDTO(BaseModel):
    """The archetypes each mealtime chooses from, ``data/archetypes.yaml``."""

    model_config = ConfigDict(extra="forbid")

    breakfast: list[ArchetypeDTO] = Field(
        default_factory=list, description="The archetypes breakfast chooses from"
    )
    lunch: list[ArchetypeDTO] = Field(
        default_factory=list, description="The archetypes lunch chooses from"
    )
    dinner: list[ArchetypeDTO] = Field(
        default_factory=list, description="The archetypes dinner chooses from"
    )
    snacks: list[ArchetypeDTO] = Field(
        default_factory=list, description="The archetypes snacks chooses from"
    )
