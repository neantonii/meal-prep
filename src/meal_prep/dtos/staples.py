"""Staples DTO — the shape of the gitignored ``diary/staples.yaml``.

Ingredients the user always has on hand (oils, spices, sauces): the session
shopping checklist counts them as had in every session. Parsing of the file
lives in ``meal_prep.adapters.staples``.

Compatibility rule (as for diary weeks): fields are only ever added, never
renamed or removed; a field added later must be optional.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from meal_prep.dtos._normalize import normalize_slug


class StaplesDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    always_have: list[str] = Field(
        default_factory=list,
        description="Ingredient ids always on hand, in every session",
    )

    @field_validator("always_have")
    @classmethod
    def validate_ids(cls, v: list[str]) -> list[str]:
        return sorted({normalize_slug(i, field="Staple ingredient id") for i in v})
