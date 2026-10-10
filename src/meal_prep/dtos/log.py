"""Log DTOs — the shape of a gitignored weekly eating log.

A log week is a dated record of what was eaten: days with up to four
mealtime slots (breakfast/lunch/dinner/snacks), each holding an ordered list
of recipe ids (one serving each, duplicates allowed). Parsing of
``logs/*.yaml`` files lives in ``meal_prep.adapters.logs``.
"""

from __future__ import annotations

import datetime
import itertools
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from meal_prep.dtos._normalize import normalize_slug
from meal_prep.enums import Mealtime


class LoggedSlotDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mealtime: Mealtime = Field(..., description="Which of the four daily slots")
    recipes: list[str] = Field(
        ...,
        min_length=1,
        description="Ordered recipe ids, one serving each; duplicates allowed",
    )

    @field_validator("recipes")
    @classmethod
    def validate_recipe_ids(cls, v: list[str]) -> list[str]:
        return [normalize_slug(item, field="Logged recipe id") for item in v]


class LogDayDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: datetime.date = Field(..., description="Calendar day this entry records")
    slots: list[LoggedSlotDTO] = Field(
        default_factory=list, description="Eaten slots in mealtime order"
    )

    @field_validator("slots")
    @classmethod
    def validate_slot_order(cls, v: list[LoggedSlotDTO]) -> list[LoggedSlotDTO]:
        seen: set[Mealtime] = set()
        for slot in v:
            if slot.mealtime in seen:
                raise ValueError(
                    f"Duplicate mealtime '{slot.mealtime.value}' in one day"
                )
            seen.add(slot.mealtime)
        return sorted(v, key=lambda slot: list(Mealtime).index(slot.mealtime))


class LogWeekDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    week: str = Field(
        ...,
        pattern=r"^\d{4}-W\d{2}$",
        description="ISO week label, e.g. 2026-W42",
    )
    days: list[LogDayDTO] = Field(
        ..., min_length=1, description="Logged days in date order"
    )
    source_path: Path | None = None

    @field_validator("days")
    @classmethod
    def validate_day_order(cls, v: list[LogDayDTO]) -> list[LogDayDTO]:
        for prev, curr in itertools.pairwise(v):
            if curr.date <= prev.date:
                raise ValueError("Log days must be in strictly increasing date order")
        return v
