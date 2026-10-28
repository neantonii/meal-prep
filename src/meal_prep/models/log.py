"""Enriched log values — the frozen, fully-resolved form of a weekly log.

A ``LogWeek`` here is *not* the authored document (that is the ``LogWeekDTO``
in ``meal_prep.dtos.log``); it is computed once by
``meal_prep.services.logs.prepare_log_week`` and never constructed from a file
directly. Each mealtime resolves to entries in authored order (duplicates
preserved — each entry is one serving) with summed cost/macros aggregates,
with no hidden state.

A ``LogEntry`` carries its own title, cost and macros: the numbers frozen when
the entry was logged (#107), never looked up in current recipes. Its
``session_id`` names the prep session it came from (``models.session``).

Frozen dataclass value objects: no collaborators, no I/O, no mutation.
Methods are pure functions of the fields alone. All amounts are raw floats
with no rounding — presentation is the report's concern.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from functools import reduce

from meal_prep.enums import Mealtime
from meal_prep.models.ingredient import MacrosInfo


@dataclass(frozen=True, slots=True)
class LogEntry:
    """One logged serving: its id, which recipe, its frozen per-serving
    title, cost and macros, and the prep session it came from (if any)."""

    entry_id: str
    recipe_id: str
    title: str
    cost: float
    macros: MacrosInfo
    session_id: str | None = None


@dataclass(frozen=True, slots=True)
class LoggedMeal:
    """One eaten mealtime: its entries plus aggregates."""

    mealtime: Mealtime
    entries: tuple[LogEntry, ...]

    @property
    def recipe_ids(self) -> tuple[str, ...]:
        """Recipe ids in order (duplicates preserved)."""
        return tuple(entry.recipe_id for entry in self.entries)

    @property
    def cost(self) -> float:
        """Meal cost at one serving per entry (raw; renderer rounds)."""
        return sum(entry.cost for entry in self.entries)

    @property
    def macros(self) -> MacrosInfo:
        """Summed per-serving macros over all entries (raw, unrounded)."""
        return reduce(
            MacrosInfo.added,
            (entry.macros for entry in self.entries),
            MacrosInfo.zero(),
        )


@dataclass(frozen=True, slots=True)
class LogDay:
    """One logged day: four fixed mealtime fields, absent when not logged."""

    date: datetime.date
    breakfast: tuple[LogEntry, ...] | None = None
    lunch: tuple[LogEntry, ...] | None = None
    dinner: tuple[LogEntry, ...] | None = None
    snacks: tuple[LogEntry, ...] | None = None

    def meal(self, mealtime: Mealtime) -> LoggedMeal | None:
        """Return the meal for ``mealtime``, or ``None`` when not logged."""
        entries = getattr(self, mealtime.value)
        if entries is None:
            return None
        return LoggedMeal(mealtime=mealtime, entries=entries)

    def meals(self) -> tuple[LoggedMeal, ...]:
        """Logged meals in ``Mealtime`` enum order."""
        return tuple(
            meal for mealtime in Mealtime if (meal := self.meal(mealtime)) is not None
        )

    @property
    def cost(self) -> float:
        """Day cost summed over logged mealtimes."""
        return sum(meal.cost for meal in self.meals())

    @property
    def macros(self) -> MacrosInfo:
        """Day macros summed over logged mealtimes."""
        return reduce(
            MacrosInfo.added,
            (meal.macros for meal in self.meals()),
            MacrosInfo.zero(),
        )


@dataclass(frozen=True, slots=True)
class LogWeek:
    """A resolved log week: days in date order plus aggregates."""

    week: str
    days: tuple[LogDay, ...]

    @property
    def total_cost(self) -> float:
        """Week cost summed over days."""
        return sum(day.cost for day in self.days)

    @property
    def total_macros(self) -> MacrosInfo:
        """Week macros summed over days."""
        return reduce(
            MacrosInfo.added,
            (day.macros for day in self.days),
            MacrosInfo.zero(),
        )
