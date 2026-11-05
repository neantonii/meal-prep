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
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from meal_prep.dtos._normalize import normalize_slug

# The one definition of a week id's shape. Match it with ``fullmatch``: a
# ``$``-anchored ``re.match`` would also accept a trailing newline.
WEEK_ID = re.compile(r"(\d{4})-W(\d{2})")


# The numbers a free-form entry must carry: what totals are made of.
REQUIRED_FREE = ("calories_kcal", "protein_g", "fat_g", "carbs_g")

# Every number an entry carries, in file order.
NUMBERS = (
    "cost",
    "calories_kcal",
    "protein_g",
    "fat_g",
    "carbs_g",
    "fiber_g",
    "saturated_fat_g",
    "sugars_g",
    "sodium_mg",
    "potassium_mg",
)


class EntryEstimateDTO(BaseModel):
    """How a free-form entry's numbers were guessed (absent: they are known,
    e.g. from the menu or label)."""

    model_config = ConfigDict(extra="forbid")

    source: Literal["manual", "ai"] = Field(
        ..., description="Typed in by hand, or estimated by AI"
    )
    kcal_low: float | None = Field(
        default=None, ge=0, description="Low end of the calories range, if given"
    )
    kcal_high: float | None = Field(
        default=None, ge=0, description="High end of the calories range, if given"
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="What the estimate assumed (size, oil, sauce...)",
    )


class DiaryEntryDTO(BaseModel):
    """One eaten serving, with the numbers as they were when it was logged.

    A recipe entry names its recipe and carries every number. A free-form
    entry (takeout, eating out) has no recipe: a title, calories and the
    three macros for one portion (the other numbers, cost included, may be
    absent = unknown), and whether the numbers are an estimate. It is never
    linked to a prep session.
    """

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID = Field(..., description="Entry id (UUID); never changes")
    recipe: str | None = Field(
        default=None,
        description="Id of the recipe that was eaten; absent for a free-form "
        "entry (takeout, eating out)",
    )
    title: str = Field(
        ..., min_length=1, description="Recipe title when the entry was logged"
    )
    cost: float | None = Field(
        default=None, ge=0, description="Cost of one serving when logged, in CAD"
    )
    calories_kcal: float | None = Field(
        default=None, ge=0, description="Per serving, when logged"
    )
    protein_g: float | None = Field(
        default=None, ge=0, description="Per serving, when logged"
    )
    fat_g: float | None = Field(
        default=None, ge=0, description="Per serving, when logged"
    )
    carbs_g: float | None = Field(
        default=None, ge=0, description="Per serving, when logged"
    )
    fiber_g: float | None = Field(
        default=None, ge=0, description="Per serving, when logged"
    )
    saturated_fat_g: float | None = Field(
        default=None, ge=0, description="Per serving, when logged"
    )
    sugars_g: float | None = Field(
        default=None, ge=0, description="Per serving, when logged"
    )
    sodium_mg: float | None = Field(
        default=None, ge=0, description="Per serving, when logged"
    )
    potassium_mg: float | None = Field(
        default=None, ge=0, description="Per serving, when logged"
    )
    session: uuid.UUID | None = Field(
        default=None,
        description="Id of the prep session this serving came from; absent when "
        "not from a session",
    )
    estimate: EntryEstimateDTO | None = Field(
        default=None,
        description="Free-form entries: present when the numbers are a guess",
    )

    @field_validator("recipe")
    @classmethod
    def validate_recipe_id(cls, v: str | None) -> str | None:
        return None if v is None else normalize_slug(v, field="Logged recipe id")

    @model_validator(mode="after")
    def validate_kind(self) -> DiaryEntryDTO:
        """A recipe entry carries every number; a free-form one at least
        calories and the macros, may record an estimate, and is never linked
        to a prep session."""
        required = NUMBERS if self.recipe is not None else REQUIRED_FREE
        missing = [name for name in required if getattr(self, name) is None]
        if missing:
            kind = "Recipe" if self.recipe is not None else "Free-form"
            raise ValueError(f"{kind} entry is missing {', '.join(missing)}")
        if self.recipe is not None and self.estimate is not None:
            raise ValueError("Only free-form entries have an estimate")
        if self.recipe is None and self.session is not None:
            raise ValueError("A free-form entry is never linked to a prep session")
        return self

    @property
    def free_form(self) -> bool:
        """Takeout or eating out: no recipe."""
        return self.recipe is None


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
