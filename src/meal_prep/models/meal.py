"""Enriched meal value — the frozen, fully-resolved form of a meal.

A ``Meal`` here is *not* the authored document (that is the ``MealDTO`` in
``meal_prep.dtos.meal``); it is computed once by
``meal_prep.services.meals.prepare_meal`` and never constructed from a file
directly. It carries the resolved recipes in authored order (duplicates
preserved — each entry is one serving) and the summed cost/macros aggregates
a consumer needs, with no hidden state.

Frozen dataclass value object: no collaborators, no I/O, no mutation. Methods
are pure functions of the fields alone. All amounts are raw floats with no
rounding — presentation is the renderer's concern.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import reduce
from pathlib import Path

from meal_prep.models.ingredient import MacrosInfo
from meal_prep.models.recipe import Recipe


@dataclass(frozen=True, slots=True)
class Meal:
    """An enriched, immutable meal ready for downstream computation."""

    id: str
    title: str
    recipes: tuple[Recipe, ...]
    source_path: Path | None = None

    @property
    def recipe_ids(self) -> tuple[str, ...]:
        """Authored recipe ids in order (duplicates preserved)."""
        return tuple(recipe.id for recipe in self.recipes)

    @property
    def total_cost(self) -> float:
        """Total cost at one serving per entry (raw; renderer rounds)."""
        return sum(recipe.cost_per_portion for recipe in self.recipes)

    @property
    def total_macros(self) -> MacrosInfo:
        """Summed per-serving macros over all entries (raw, unrounded)."""
        return reduce(
            MacrosInfo.added,
            (recipe.per_serving_macros for recipe in self.recipes),
            MacrosInfo.zero(),
        )

    @property
    def total_cooked_g(self) -> float:
        """Summed per-serving cooked weight (raw; renderer rounds)."""
        return sum(recipe.portion_cooked_g for recipe in self.recipes)
