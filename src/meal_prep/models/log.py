"""Enriched log values — the frozen, fully-resolved form of a weekly log.

A ``LogWeek`` here is *not* the authored document (that is the ``LogWeekDTO``
in ``meal_prep.dtos.log``); it is computed once by
``meal_prep.services.logs.prepare_log_week`` and never constructed from a file
directly. Each mealtime resolves to recipes in authored order (duplicates
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

from meal_prep.enums import Mealtime
from meal_prep.models.ingredient import MacrosInfo
from meal_prep.models.recipe import Recipe


@dataclass(frozen=True, slots=True)
class LoggedMeal:
    """One eaten mealtime: resolved recipes plus aggregates."""

    mealtime: Mealtime
    recipes: tuple[Recipe, ...]

    @property
    def recipe_ids(self) -> tuple[str, ...]:
        """Authored recipe ids in order (duplicates preserved)."""
        return tuple(recipe.id for recipe in self.recipes)

    @property
    def cost(self) -> float:
        """Meal cost at one serving per entry (raw; renderer rounds)."""
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
    """One logged day: four fixed mealtime fields, absent when not logged."""

    date: datetime.date
    breakfast: tuple[Recipe, ...] | None = None
    lunch: tuple[Recipe, ...] | None = None
    dinner: tuple[Recipe, ...] | None = None
    snacks: tuple[Recipe, ...] | None = None

    def meal(self, mealtime: Mealtime) -> LoggedMeal | None:
        """Return the meal for ``mealtime``, or ``None`` when not logged."""
        recipes = getattr(self, mealtime.value)
        if recipes is None:
            return None
        return LoggedMeal(mealtime=mealtime, recipes=recipes)

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
