"""Meal DTO — an authored rigid set of recipes.

A meal is an ordered collection of recipe ids (e.g. eggs + toast + coffee).
Portions are implicitly one serving per entry; listing an id twice means two
servings. Parsing of ``meals/*.yaml`` files lives in
``meal_prep.adapters.meals``.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from meal_prep.dtos._normalize import normalize_slug


class MealDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Unique slug matching the file stem")
    title: str = Field(..., min_length=1, description="Human-readable meal title")
    recipes: list[str] = Field(
        ...,
        min_length=1,
        description="Ordered recipe ids, one serving each; duplicates allowed",
    )
    source_path: Path | None = None

    @field_validator("id")
    @classmethod
    def validate_id_format(cls, v: str) -> str:
        return normalize_slug(v, field="Meal id")

    @field_validator("recipes")
    @classmethod
    def validate_recipe_ids(cls, v: list[str]) -> list[str]:
        return [normalize_slug(item, field="Meal recipe id") for item in v]
