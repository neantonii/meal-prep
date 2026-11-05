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

import datetime
from dataclasses import dataclass
from functools import reduce

from meal_prep.enums import Mealtime
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


@dataclass(frozen=True, slots=True)
class MealSlot:
    """One meal to fill: a day, a mealtime and the session that feeds it."""

    date: datetime.date
    mealtime: Mealtime
    session: datetime.date


@dataclass(frozen=True, slots=True)
class SlotPick:
    """One recipe placed in a slot (a slot may hold several)."""

    slot: MealSlot
    meal: PlannedMeal


@dataclass(frozen=True, slots=True)
class KcalGoal:
    """Daily kcal: a soft daily target plus a rolling-window target.

    Each day pays ``(kcal - target)²`` (hard limits ``lo``..``hi``); each
    ``window``-day run pays ``w·(sum - window·target)²``. ``payback`` is the
    share of one day's miss the next day makes up when it is the only free
    day in its window: ``w = payback / (1 - payback)``.
    """

    target: int = 2100
    lo: int = 0
    hi: int = 4000
    window: int = 3
    payback: float = 0.5

    def __post_init__(self) -> None:
        if not 0 <= self.payback < 1:
            raise ValueError(f"payback must be in [0, 1) (got {self.payback}).")
        if self.window < 1:
            raise ValueError(f"window must be at least 1 (got {self.window}).")

    @property
    def window_weight(self) -> float:
        """Rolling-window weight relative to the daily weight of 1."""
        return self.payback / (1 - self.payback)


@dataclass(frozen=True, slots=True)
class SessionPlan:
    """One session's part of a horizon plan: its picks and batches.

    ``truncated``: the horizon ends before the session's cycle does, so it
    saw only part of its meals (its batches are a rough draft).
    """

    session: datetime.date
    truncated: bool
    picks: tuple[SlotPick, ...]
    prep: tuple[PlannedBatch, ...]

    @property
    def total_cost(self) -> float:
        """Total session cost at full batch prices (leftovers included)."""
        return sum(batch.cost for batch in self.prep)


@dataclass(frozen=True, slots=True)
class HorizonPlan:
    """Every session touching the horizon, plus each horizon day's kcal."""

    sessions: tuple[SessionPlan, ...]
    day_kcal: tuple[tuple[datetime.date, float], ...]  # fixed + planned
    objective: float = 0.0  # penalty reached, in kcal²
    bound: float = 0.0  # proven lower bound on the penalty, in kcal²
    seconds: float = 0.0  # solve wall time
