"""Frozen week-plan value — the solved assignment in domain terms.

A ``WeekPlan`` is computed once by ``meal_prep.planner.solver.plan_week`` and
never constructed by hand. Each day names its three meals explicitly
(``breakfast``/``lunch``/``dinner``).

All frozen dataclasses are value objects: no I/O, no mutation. All amounts
are raw floats with no rounding — presentation is the report's concern.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import reduce

from meal_prep.models.ingredient import MacrosInfo

DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


@dataclass(frozen=True, slots=True)
class PlannedMeal:
    """One filled meal slot: which recipe, and its per-serving cost/macros."""

    recipe_id: str
    title: str
    cost: float
    macros: MacrosInfo


@dataclass(frozen=True, slots=True)
class DailyPlannedMeal:
    """One day: a named meal per meal slot."""

    day: str
    breakfast: PlannedMeal
    lunch: PlannedMeal
    dinner: PlannedMeal

    @property
    def cost(self) -> float:
        """Total day cost."""
        return self.breakfast.cost + self.lunch.cost + self.dinner.cost

    @property
    def macros(self) -> MacrosInfo:
        """Day macros summed over the three meals."""
        morning = MacrosInfo.added(self.breakfast.macros, self.lunch.macros)
        return MacrosInfo.added(morning, self.dinner.macros)


@dataclass(frozen=True, slots=True)
class WeekPlan:
    """A solved week: 7 days plus pre-computed aggregates."""

    days: tuple[DailyPlannedMeal, ...]

    @property
    def total_cost(self) -> float:
        """Total week cost."""
        return sum(day.cost for day in self.days)

    @property
    def week_macros(self) -> MacrosInfo:
        """Week macros summed over days."""
        return reduce(
            MacrosInfo.added,
            (day.macros for day in self.days),
            MacrosInfo.zero(),
        )
