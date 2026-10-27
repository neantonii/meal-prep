"""Diary DTOs — the shape of the gitignored diary files (``diary/*.yaml``).

A diary week is a record of what was eaten: an ISO week of days with four
fixed mealtime fields (breakfast/lunch/dinner/snacks). Each mealtime is an
ordered list of entries, and every entry carries its own id plus the numbers
frozen when it was logged (#107), so past weeks never change when recipes,
ingredients or prices do. Absent mealtime means not logged; present-but-empty
is rejected. Parsing of the files lives in ``meal_prep.adapters.logs``.

Compatibility rule: entry fields are only ever added, never renamed or
removed. A field added later must be optional (absent = not recorded), so
every diary file ever written stays loadable.
"""

from __future__ import annotations

import datetime
import itertools
import re
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from meal_prep.dtos._normalize import normalize_slug

# The one definition of a week id's shape. Match it with ``fullmatch``: a
# ``$``-anchored ``re.match`` would also accept a trailing newline.
WEEK_ID = re.compile(r"(\d{4})-W(\d{2})")


class DiaryEntryDTO(BaseModel):
    """One eaten serving, with the numbers as they were when it was logged."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID = Field(..., description="Entry id (UUID); never changes")
    recipe: str = Field(..., description="Id of the recipe that was eaten")
    title: str = Field(
        ..., min_length=1, description="Recipe title when the entry was logged"
    )
    cost: float = Field(
        ..., ge=0, description="Cost of one serving when logged, in CAD"
    )
    calories_kcal: float = Field(..., ge=0, description="Per serving, when logged")
    protein_g: float = Field(..., ge=0, description="Per serving, when logged")
    fat_g: float = Field(..., ge=0, description="Per serving, when logged")
    carbs_g: float = Field(..., ge=0, description="Per serving, when logged")
    fiber_g: float = Field(..., ge=0, description="Per serving, when logged")
    saturated_fat_g: float = Field(..., ge=0, description="Per serving, when logged")
    sugars_g: float = Field(..., ge=0, description="Per serving, when logged")
    sodium_mg: float = Field(..., ge=0, description="Per serving, when logged")
    potassium_mg: float = Field(..., ge=0, description="Per serving, when logged")

    @field_validator("recipe")
    @classmethod
    def validate_recipe_id(cls, v: str) -> str:
        return normalize_slug(v, field="Logged recipe id")


class DiaryDayDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: datetime.date = Field(..., description="Calendar day this entry records")
    breakfast: list[DiaryEntryDTO] | None = Field(
        default=None, min_length=1, description="Breakfast entries in eaten order"
    )
    lunch: list[DiaryEntryDTO] | None = Field(
        default=None, min_length=1, description="Lunch entries in eaten order"
    )
    dinner: list[DiaryEntryDTO] | None = Field(
        default=None, min_length=1, description="Dinner entries in eaten order"
    )
    snacks: list[DiaryEntryDTO] | None = Field(
        default=None, min_length=1, description="Snacks entries in eaten order"
    )

    @model_validator(mode="after")
    def validate_at_least_one_meal(self) -> DiaryDayDTO:
        if (
            self.breakfast is None
            and self.lunch is None
            and self.dinner is None
            and self.snacks is None
        ):
            raise ValueError("Log day must record at least one mealtime")
        return self

    def entries(self) -> list[DiaryEntryDTO]:
        """All entries of the day, mealtime by mealtime."""
        return [
            entry
            for meal in (self.breakfast, self.lunch, self.dinner, self.snacks)
            for entry in meal or ()
        ]


class DiaryWeekDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    week: str = Field(
        ...,
        pattern=rf"^{WEEK_ID.pattern}$",
        description="ISO week label, e.g. 2026-W42; must be a real ISO week and "
        "every day must fall inside it",
    )
    days: list[DiaryDayDTO] = Field(
        ..., min_length=1, description="Logged days in date order"
    )

    @field_validator("days")
    @classmethod
    def validate_day_order(cls, v: list[DiaryDayDTO]) -> list[DiaryDayDTO]:
        for prev, curr in itertools.pairwise(v):
            if curr.date <= prev.date:
                raise ValueError("Log days must be in strictly increasing date order")
        return v

    @model_validator(mode="after")
    def validate_days_in_week(self) -> DiaryWeekDTO:
        """A week file holds only days of its own ISO week (stdlib calendar math)."""
        year, number = (int(part) for part in self.week.split("-W"))
        try:
            datetime.date.fromisocalendar(year, number, 1)
        except ValueError:
            raise ValueError(f"'{self.week}' is not a real ISO week") from None
        for day in self.days:
            if day.date.isocalendar()[:2] != (year, number):
                raise ValueError(f"Day {day.date} is outside ISO week {self.week}")
        return self

    @model_validator(mode="after")
    def validate_unique_entry_ids(self) -> DiaryWeekDTO:
        seen: set[uuid.UUID] = set()
        for day in self.days:
            for entry in day.entries():
                if entry.id in seen:
                    raise ValueError(f"Duplicate entry id {entry.id}")
                seen.add(entry.id)
        return self
