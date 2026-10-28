"""Enriched prep session values — the frozen form of a session file.

A ``PrepSession`` is *not* the authored document (that is the
``PrepSessionDTO`` in ``meal_prep.dtos.session``); it is built by
``meal_prep.services.sessions.prepare_session``. Every item carries the
numbers frozen when it was added (#107), never looked up in current recipes.

Frozen dataclass value objects: no collaborators, no I/O, no mutation.
Batches, servings and portions are whole numbers; other amounts are raw
floats with no rounding — presentation is the consumer's
concern. ``docs/prep-sessions.md`` is the spec.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from meal_prep.enums import Aisle
from meal_prep.models.ingredient import MacrosInfo


@dataclass(frozen=True, slots=True)
class PackageSize:
    """A retail package as frozen: the product title and its size."""

    product: str
    amount: float
    unit: str


@dataclass(frozen=True, slots=True)
class SessionIngredient:
    """One frozen ingredient line of one batch. ``aisle``, ``package`` and
    ``packages`` (packages per batch) are ``None`` in files older than them;
    ``packages`` is set exactly when ``package`` is."""

    ingredient_id: str
    name: str
    grams: float
    cost: float
    aisle: Aisle | None
    package: PackageSize | None
    packages: float | None


@dataclass(frozen=True, slots=True)
class NeededIngredient:
    """One ingredient a session needs on hand, summed over its batches.

    ``packages`` is a fraction of ``package``; both are ``None`` for lines
    frozen before packages were recorded.
    """

    ingredient_id: str
    name: str
    aisle: Aisle | None
    package: PackageSize | None
    packages: float | None
    grams: float
    cost: float
    recipes: tuple[str, ...]  # titles of the items that use it


@dataclass(frozen=True, slots=True)
class AisleNeeds:
    """The needed ingredients of one aisle (``None``: not recorded)."""

    aisle: Aisle | None
    ingredients: tuple[NeededIngredient, ...]

    @property
    def cost(self) -> float:
        return sum(i.cost for i in self.ingredients)


@dataclass(frozen=True, slots=True)
class SessionItem:
    """One recipe of a session with its frozen per-serving numbers."""

    recipe_id: str
    title: str
    batches: int
    servings: int  # per batch
    cost: float  # per serving
    macros: MacrosInfo  # per serving
    ingredients: tuple[SessionIngredient, ...]  # one batch

    @property
    def portions(self) -> int:
        """Portions made: batches x servings."""
        return self.batches * self.servings


@dataclass(frozen=True, slots=True)
class PrepSession:
    """A dated prep session; ``session_id`` is what diary entries link to."""

    session_id: str
    date: datetime.date
    items: tuple[SessionItem, ...]

    def item(self, recipe_id: str) -> SessionItem | None:
        """The item for ``recipe_id``, or ``None`` when not listed."""
        return next((i for i in self.items if i.recipe_id == recipe_id), None)

    def needs(self) -> tuple[AisleNeeds, ...]:
        """What to have on hand by this session: every item's ingredient lines
        times its batches, summed per ingredient (and package), grouped by
        aisle in walking order; lines without an aisle come last. Not a
        purchase list: stock already at home is not subtracted."""
        type Key = tuple[str, Aisle | None, PackageSize | None]
        lines: dict[Key, list[tuple[SessionItem, SessionIngredient]]] = {}
        for item in self.items:
            for line in item.ingredients:
                key = (line.ingredient_id, line.aisle, line.package)
                lines.setdefault(key, []).append((item, line))
        needed = [
            NeededIngredient(
                ingredient_id=ingredient_id,
                name=found[0][1].name,
                aisle=aisle,
                package=package,
                packages=(
                    None
                    if package is None
                    else sum(
                        item.batches * (line.packages or 0.0) for item, line in found
                    )
                ),
                grams=sum(item.batches * line.grams for item, line in found),
                cost=sum(item.batches * line.cost for item, line in found),
                recipes=tuple(dict.fromkeys(item.title for item, _ in found)),
            )
            for (ingredient_id, aisle, package), found in lines.items()
        ]
        order = list(Aisle)
        groups: dict[Aisle | None, list[NeededIngredient]] = {}
        for ing in sorted(needed, key=lambda i: i.name.lower()):
            groups.setdefault(ing.aisle, []).append(ing)
        return tuple(
            AisleNeeds(aisle=aisle, ingredients=tuple(ings))
            for aisle, ings in sorted(
                groups.items(),
                key=lambda g: len(order) if g[0] is None else order.index(g[0]),
            )
        )
