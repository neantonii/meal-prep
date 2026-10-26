"""Log DTOs — the shape of a gitignored weekly plan or diary file.

A log week is a dated record of what was planned or eaten: days with four fixed
mealtime fields (breakfast/lunch/dinner/snacks), each holding an ordered list
of recipe ids (one serving each, duplicates allowed). Absent means not
logged; present-but-empty is rejected. Parsing of ``plans/*.yaml`` and
``diary/*.yaml`` files lives in ``meal_prep.adapters.logs``.
"""

from __future__ import annotations

import datetime
import itertools

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from meal_prep.dtos._normalize import normalize_slug


class LogDayDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: datetime.date = Field(..., description="Calendar day this entry records")
    breakfast: list[str] | None = Field(
        default=None, min_length=1, description="Breakfast recipe ids in eaten order"
    )
    lunch: list[str] | None = Field(
        default=None, min_length=1, description="Lunch recipe ids in eaten order"
    )
    dinner: list[str] | None = Field(
        default=None, min_length=1, description="Dinner recipe ids in eaten order"
    )
    snacks: list[str] | None = Field(
        default=None, min_length=1, description="Snacks recipe ids in eaten order"
    )

    @field_validator("breakfast", "lunch", "dinner", "snacks")
    @classmethod
    def validate_recipe_ids(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        return [normalize_slug(item, field="Logged recipe id") for item in v]

    @model_validator(mode="after")
    def validate_at_least_one_meal(self) -> LogDayDTO:
        if (
            self.breakfast is None
            and self.lunch is None
            and self.dinner is None
            and self.snacks is None
        ):
            raise ValueError("Log day must record at least one mealtime")
        return self


class LogWeekDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    week: str = Field(
        ...,
        pattern=r"^\d{4}-W\d{2}$",
        description="ISO week label, e.g. 2026-W42; must be a real ISO week and "
        "every day must fall inside it",
    )
    days: list[LogDayDTO] = Field(
        ..., min_length=1, description="Logged days in date order"
    )

    @field_validator("days")
    @classmethod
    def validate_day_order(cls, v: list[LogDayDTO]) -> list[LogDayDTO]:
        for prev, curr in itertools.pairwise(v):
            if curr.date <= prev.date:
                raise ValueError("Log days must be in strictly increasing date order")
        return v

    @model_validator(mode="after")
    def validate_days_in_week(self) -> LogWeekDTO:
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
