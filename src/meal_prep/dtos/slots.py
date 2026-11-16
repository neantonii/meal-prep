"""Slot DTOs — the shape of the gitignored ``diary/unassigned.yaml`` and
``diary/bin.yaml``.

A portion of a prep session is a meal with a home: a day (a week file), the
unassigned slot (cooked or planned, no day yet) or the bin (thrown away).
The two slots without a date hold ordinary recipe entries, each linked to
its session (``docs/freezer.md``). Parsing lives in
``meal_prep.adapters.slots``.

Compatibility rule (as for diary weeks): fields are only ever added, never
renamed or removed; a field added later must be optional.
"""

from __future__ import annotations

import datetime
import uuid
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator

from meal_prep.dtos.log import RecipeEntryDTO


class BinnedEntryDTO(RecipeEntryDTO):
    """A portion thrown away, and the day it went to the bin."""

    binned: datetime.date = Field(..., description="Day the portion was binned")


def _check(meals: Sequence[RecipeEntryDTO]) -> None:
    seen: set[uuid.UUID] = set()
    for meal in meals:
        if meal.session is None:
            raise ValueError(f"{meal.title} ({meal.id}) has no prep session")
        if meal.id in seen:
            raise ValueError(f"Duplicate entry id {meal.id}")
        seen.add(meal.id)


class UnassignedDTO(BaseModel):
    """Portions with no day yet, ``diary/unassigned.yaml``."""

    model_config = ConfigDict(extra="forbid")

    meals: list[RecipeEntryDTO] = Field(
        default_factory=list,
        description="Portions of prep sessions that are on no day; each "
        "names its session",
    )

    @field_validator("meals")
    @classmethod
    def validate_meals(cls, v: list[RecipeEntryDTO]) -> list[RecipeEntryDTO]:
        _check(v)
        return v


class BinDTO(BaseModel):
    """Portions thrown away, ``diary/bin.yaml``."""

    model_config = ConfigDict(extra="forbid")

    meals: list[BinnedEntryDTO] = Field(
        default_factory=list,
        description="Portions of prep sessions that were thrown away; each "
        "names its session",
    )

    @field_validator("meals")
    @classmethod
    def validate_meals(cls, v: list[BinnedEntryDTO]) -> list[BinnedEntryDTO]:
        _check(v)
        return v
