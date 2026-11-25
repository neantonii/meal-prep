"""The resolved library — every authored ingredient, recipe and meal, enriched.

A ``Library`` is the single value consumers (renderers, reports, the planner,
the diary server) work from. It is built once by
``meal_prep.library.load_library`` and holds only enriched models: no DTOs,
no units taxonomy, no equipment registry. Those are inputs to enrichment and
are already folded into each ``Ingredient`` (conversion graph) and ``Recipe``
(equipment names).

Frozen, read-only mappings keyed by id; the whole dataset fits in memory.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from meal_prep.enums import Mealtime
from meal_prep.models.archetype import Archetype
from meal_prep.models.ingredient import Ingredient
from meal_prep.models.meal import Meal
from meal_prep.models.recipe import Recipe


@dataclass(frozen=True, slots=True)
class Library:
    """All enriched ingredients, recipes and meals, keyed by id, and the
    meal archetypes each mealtime chooses from (the planner's)."""

    ingredients: Mapping[str, Ingredient]
    recipes: Mapping[str, Recipe]
    meals: Mapping[str, Meal]
    archetypes: Mapping[Mealtime, tuple[Archetype, ...]]
