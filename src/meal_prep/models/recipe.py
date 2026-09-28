"""Enriched recipe value — the frozen, fully-resolved form of a recipe.

A ``Recipe`` here is *not* the authored document (that is the DTO of the same
name in ``meal_prep.dtos.recipe``); it is computed once by
``meal_prep.services.recipes.prepare_recipe`` and never constructed from a file
directly. It carries the resolved, gram-based ingredient breakdown and the
pre-computed batch/per-serving aggregates a consumer needs, with no hidden
state.

Both frozen dataclasses are value objects: no collaborators, no I/O, no
mutation. Methods are pure functions of the fields alone. All amounts are raw
floats with no rounding — presentation is the renderer's concern.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import reduce
from pathlib import Path

from meal_prep.enums import RecipeCategory
from meal_prep.models.ingredient import MacrosInfo


@dataclass(frozen=True, slots=True)
class RecipeIngredient:
    """One ingredient line, merged and resolved.

    ``grams`` is the canonical internal amount (merged, raw) that ``cost`` and
    ``macros`` are derived from. ``quantity``/``unit`` are the display amount,
    using the ingredient's first-authored unit (Cooklang's "fallback to first
    occurrence"): a single reference is shown verbatim; duplicate references are
    converted into that first unit and summed. ``repeated`` is true when the
    ingredient was declared with an amount more than once — the renderer uses it
    to show an amount inline in the steps only when it is genuinely needed.
    All amounts are raw and unrounded.
    """

    id: str
    name: str
    step_name: str
    quantity: float
    unit: str
    grams: float
    cost: float
    macros: MacrosInfo
    repeated: bool = False


@dataclass(frozen=True, slots=True)
class Recipe:
    """An enriched, immutable recipe ready for downstream computation."""

    id: str
    title: str
    category: RecipeCategory
    servings: float
    cooked_g: float
    fridge_days: int
    freezer_friendly: bool
    equipment: tuple[str, ...]  # resolved display names, in authored order
    equipment_by_id: Mapping[str, str]  # canonical id -> display name
    ingredients: tuple[RecipeIngredient, ...]
    instructions: str
    source_path: Path | None = None

    # ------------------------------------------------------------------
    # Pure aggregates of the fields above (raw, unrounded).
    # ------------------------------------------------------------------

    @property
    def batch_g(self) -> float:
        """Total raw ingredient weight in grams."""
        return sum(ing.grams for ing in self.ingredients)

    @property
    def total_cost(self) -> float:
        """Total batch cost."""
        return sum(ing.cost for ing in self.ingredients)

    @property
    def cost_per_portion(self) -> float:
        """Cost per portion (raw; renderer rounds)."""
        return self.total_cost / self.servings

    @property
    def portion_cooked_g(self) -> float:
        """Cooked weight per portion (raw; renderer rounds)."""
        return self.cooked_g / self.servings

    @property
    def batch_macros(self) -> MacrosInfo:
        """Sum of every ingredient's macro contribution."""
        return reduce(MacrosInfo.added, (ing.macros for ing in self.ingredients), MacrosInfo.zero())

    @property
    def per_serving_macros(self) -> MacrosInfo:
        """Batch macros divided by servings (raw; renderer rounds)."""
        return self.batch_macros.scaled(1.0 / self.servings)
