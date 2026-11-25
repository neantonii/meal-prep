"""Archetypes: what a meal looks like (``docs/planner.md``, "Archetypes").

Authored in ``data/archetypes.yaml`` (the one place recipe groupings
live: recipes never say which role they play), validated against the
recipes by ``meal_prep.services.archetypes`` and held by the ``Library``
per mealtime. The planner reads them; nothing here solves anything.
"""

from __future__ import annotations

from dataclasses import dataclass

from meal_prep.enums import RecipeCategory

# A takeout meal: a dish with no recipe and no session.
TAKEOUT = "takeout"


@dataclass(frozen=True, slots=True)
class Role:
    """One part of an archetype: dishes from a pool, a target count range,
    and the points for each dish short of or over it. The pool is recipe
    categories plus named recipes (``TAKEOUT`` for eating out)."""

    name: str
    categories: frozenset[RecipeCategory] = frozenset()
    recipe_ids: frozenset[str] = frozenset()
    count: tuple[int, int] = (1, 1)
    missing: float = 3.0
    extra: float = 1.0

    def accepts(self, recipe_id: str, category: RecipeCategory | None) -> bool:
        """Whether a dish belongs to this role's pool."""
        return recipe_id in self.recipe_ids or (
            category is not None and category in self.categories
        )


@dataclass(frozen=True, slots=True)
class Archetype:
    """What a meal looks like (``docs/planner.md``, "Archetypes").

    A slot chooses one archetype among those its mealtime allows and pays
    for how badly its dishes fit: each role's shortfall and excess, plus
    ``unknown`` for each dish no role takes. ``base_cost`` is paid for
    choosing it at all. ``plannable``: the planner may pick it for a slot
    with nothing pinned (takeout can only be matched, never planned).
    A dish may be in the pool of one role only.
    """

    name: str
    roles: tuple[Role, ...]
    base_cost: float = 0.0
    unknown: float = 1.0
    plannable: bool = True
