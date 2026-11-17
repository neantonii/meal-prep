"""The planner's input and output, as plain frozen values (``docs/planner.md``).

Input: the slots to fill (a day, a mealtime and the session that feeds it),
a template per mealtime (what a slot may hold), what is already eaten or
placed on each day, and the weights of the soft terms. Output: the recipes
picked per slot, the batches each session cooks, and the points per term.

No solver code here: ``meal_prep.planner.solver`` builds and solves the
model; writing a plan into the diary is the services' job.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from meal_prep.enums import Mealtime, RecipeCategory


@dataclass(frozen=True, slots=True)
class MealSlot:
    """One meal to fill: a day, a mealtime and the session that feeds it."""

    date: datetime.date
    mealtime: Mealtime
    session: datetime.date


@dataclass(frozen=True, slots=True)
class Role:
    """One part of a meal: exactly one recipe from these categories or ids."""

    name: str
    categories: frozenset[RecipeCategory] = frozenset()
    recipe_ids: frozenset[str] = frozenset()

    def accepts(self, recipe_id: str, category: RecipeCategory) -> bool:
        """Whether a recipe can fill this role."""
        return recipe_id in self.recipe_ids or category in self.categories


@dataclass(frozen=True, slots=True)
class Option:
    """One way to make a meal: each role filled by exactly one recipe.

    A fixed set of recipes (a breakfast eaten as a whole) is an option whose
    roles each name one recipe.
    """

    name: str
    roles: tuple[Role, ...]


@dataclass(frozen=True, slots=True)
class MealTemplate:
    """What a slot holds: exactly one of ``options``, plus any number of
    ``extras`` (the escape hatch). Nothing else goes in the slot. A recipe
    may fill roles of one option only."""

    options: tuple[Option, ...]
    extras: Role | None = None


@dataclass(frozen=True, slots=True)
class Weights:
    """Points per unit of each soft term (``docs/planner.md``, "Terms")."""

    leftover: float = 1.0  # per portion cooked but not placed on a day
    next_day_repeat: float = 1.0  # per recipe eaten on two days in a row


@dataclass(frozen=True, slots=True)
class SlotPick:
    """One recipe placed in a slot (a slot may hold several)."""

    slot: MealSlot
    recipe_id: str


@dataclass(frozen=True, slots=True)
class PlannedBatch:
    """What one session cooks of one recipe, and how many portions the plan
    eats; the rest are leftovers."""

    session: datetime.date
    recipe_id: str
    batches: int
    servings: int
    used: int

    @property
    def leftover(self) -> int:
        """Portions cooked but not placed on a day."""
        return self.batches * self.servings - self.used


@dataclass(frozen=True, slots=True)
class Plan:
    """A solved plan: the picks, the batches, and the points per term."""

    picks: tuple[SlotPick, ...]
    batches: tuple[PlannedBatch, ...]
    points: tuple[tuple[str, float], ...]

    @property
    def total_points(self) -> float:
        """The objective: every term's points summed."""
        return sum(value for _, value in self.points)
