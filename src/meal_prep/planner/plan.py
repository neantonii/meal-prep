"""Frozen week-plan value — the solved assignment in domain terms.

A ``WeekPlan`` is computed once by ``meal_prep.planner.solver.plan_week`` and
never constructed by hand. Each day names its three meals explicitly
(``breakfast``/``lunch``/``dinner``); ``prep`` lists the batches to cook so
the week's portions are covered (``portions_used <= batches * servings`` —
leftovers are tolerated and charged at full batch cost).

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
class PlannedBatch:
    """One prep-list line: how many batches of a recipe to cook.

    ``portions_made`` is ``batches * servings``; ``portions_used`` counts the
    week's meals assigned to this recipe (never more than made).
    """

    recipe_id: str
    title: str
    batches: int
    servings: int
    portions_used: int
    cost: float

    @property
    def portions_made(self) -> int:
        """Portions produced by the cooked batches."""
        return self.batches * self.servings

    @property
    def leftover(self) -> int:
        """Made but uneaten portions."""
        return self.portions_made - self.portions_used


@dataclass(frozen=True, slots=True)
class WeekPlan:
    """A solved week: 7 days, the batches to cook, plus aggregates."""

    days: tuple[DailyPlannedMeal, ...]
    prep: tuple[PlannedBatch, ...] = ()

    @property
    def total_cost(self) -> float:
        """Total week cost at full batch prices (leftovers included)."""
        return sum(batch.cost for batch in self.prep)

    @property
    def week_macros(self) -> MacrosInfo:
        """Week macros summed over days."""
        return reduce(
            MacrosInfo.added,
            (day.macros for day in self.days),
            MacrosInfo.zero(),
        )
