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

from meal_prep.models.ingredient import MacrosInfo


@dataclass(frozen=True, slots=True)
class SessionIngredient:
    """One frozen ingredient line of one batch."""

    ingredient_id: str
    name: str
    grams: float
    cost: float


@dataclass(frozen=True, slots=True)
class SessionItem:
    """One recipe of a session with its frozen per-serving numbers."""

    recipe_id: str
    title: str
    batches: int
    ad_hoc: bool
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
