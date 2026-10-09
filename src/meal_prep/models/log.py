"""Enriched log values — the frozen, fully-resolved form of a weekly log.

A ``LogWeek`` here is *not* the authored document (that is the ``LogWeekDTO``
in ``meal_prep.dtos.log``); it is computed once by
``meal_prep.services.logs.prepare_log_week`` and never constructed from a file
directly. Each slot resolves to recipes in authored order (duplicates
preserved — each entry is one serving) with summed cost/macros aggregates,
with no hidden state.

Frozen dataclass value objects: no collaborators, no I/O, no mutation.
Methods are pure functions of the fields alone. All amounts are raw floats
with no rounding — presentation is the report's concern.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from functools import reduce
from pathlib import Path

from meal_prep.enums import Mealtime
from meal_prep.models.ingredient import MacrosInfo
from meal_prep.models.recipe import Recipe


@dataclass(frozen=True, slots=True)
class LoggedSlot:
    """One eaten mealtime slot: resolved recipes plus aggregates."""

    mealtime: Mealtime
    recipes: tuple[Recipe, ...]

    @property
    def recipe_ids(self) -> tuple[str, ...]:
        """Authored recipe ids in order (duplicates preserved)."""
        return tuple(recipe.id for recipe in self.recipes)

    @property
    def cost(self) -> float:
        """Slot cost at one serving per entry (raw; renderer rounds)."""
        return sum(recipe.cost_per_portion for recipe in self.recipes)

    @property
    def macros(self) -> MacrosInfo:
        """Summed per-serving macros over all entries (raw, unrounded)."""
        return reduce(
            MacrosInfo.added,
            (recipe.per_serving_macros for recipe in self.recipes),
            MacrosInfo.zero(),
        )


@dataclass(frozen=True, slots=True)
class LogDay:
    """One logged day: eaten slots in mealtime order."""

    date: datetime.date
    slots: tuple[LoggedSlot, ...] = ()

    def slot(self, mealtime: Mealtime) -> LoggedSlot | None:
        """Return the slot for ``mealtime``, or ``None`` when not logged."""
        for slot in self.slots:
            if slot.mealtime is mealtime:
                return slot
        return None

    @property
    def cost(self) -> float:
        """Day cost summed over logged slots."""
        return sum(slot.cost for slot in self.slots)

    @property
    def macros(self) -> MacrosInfo:
        """Day macros summed over logged slots."""
        return reduce(
            MacrosInfo.added,
            (slot.macros for slot in self.slots),
            MacrosInfo.zero(),
        )


@dataclass(frozen=True, slots=True)
class LogWeek:
    """A resolved log week: days in date order plus aggregates."""

    week: str
    days: tuple[LogDay, ...]
    source_path: Path | None = None

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
