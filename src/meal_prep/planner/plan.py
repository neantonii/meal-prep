"""The planner's input and output, as plain frozen values (``docs/planner.md``).

Input: the days to plan (and the history days before them), what is
already in each slot (pins), the sessions with their batches and stock,
and the archetypes each mealtime allows. Output: the dishes the plan adds
per slot (with the session they come from), the batches each session
cooks, and the points per term.

No solver code here: ``meal_prep.planner.solver`` builds and solves the
model; writing a plan into the diary is the services' job.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from meal_prep.enums import Mealtime, RecipeCategory

# A pinned takeout meal: a dish with no recipe and no session.
TAKEOUT = "takeout"


@dataclass(frozen=True, slots=True)
class Slot:
    """One mealtime of one day, and the session that cooks for it."""

    date: datetime.date
    mealtime: Mealtime
    cycle: datetime.date  # the session day whose cycle the meal belongs to


@dataclass(frozen=True, slots=True)
class Pin:
    """A dish already in a slot: a recipe portion of a session (``session``
    ``None`` for an older meal without one), or takeout (``recipe_id`` is
    ``TAKEOUT``). Pins only fix variables."""

    date: datetime.date
    mealtime: Mealtime
    recipe_id: str
    session: datetime.date | None = None


@dataclass(frozen=True, slots=True)
class Batch:
    """What a session already has of one recipe.

    ``outside``: its meals the model does not see as slots (days outside the
    plan, binned). ``unassigned``: its portions with no day, free to place.
    ``fixed``: a cooked session; its batch count can't change.
    """

    session: datetime.date
    recipe_id: str
    batches: int
    servings: int
    outside: int = 0
    unassigned: int = 0
    fixed: bool = False
    fridge_days: int | None = None
    freezer_friendly: bool | None = None


@dataclass(frozen=True, slots=True)
class Role:
    """One part of an archetype: dishes from a pool, a target count range,
    and the points for each dish short of or over it."""

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


def split(name: str, *roles: Role, base_cost: float = 0.0) -> Archetype:
    """Several roles, one dish each (a plate: protein + carb + veg)."""
    return Archetype(name, roles, base_cost=base_cost)


def single(name: str, role: Role, base_cost: float = 0.0) -> Archetype:
    """One dish from one pool (a one-dish meal)."""
    return Archetype(name, (role,), base_cost=base_cost)


@dataclass(frozen=True, slots=True)
class Weights:
    """Points per unit of the event terms (``docs/planner.md``, "Terms")."""

    leftover: float = 1.0  # per portion cooked and not eaten in the plan
    next_day_repeat: float = 1.0  # per recipe eaten on two days in a row
    same_day_repeat: float = 5.0  # per extra use of a recipe in one day


@dataclass(frozen=True, slots=True)
class Problem:
    """Everything the solver needs.

    ``slots`` are the days to plan; ``history`` the days before, fully
    pinned (their dishes count for repeats). ``sessions``: every session
    day the plan may cook in (open sessions in the horizon). ``truncated``:
    sessions whose cycle runs past the horizon; their leftovers are not
    charged.
    """

    slots: tuple[Slot, ...]
    history: tuple[Slot, ...]
    pins: tuple[Pin, ...]
    batches: tuple[Batch, ...]
    sessions: tuple[datetime.date, ...]
    archetypes: dict[Mealtime, tuple[Archetype, ...]]
    truncated: frozenset[datetime.date] = frozenset()
    weights: Weights = field(default_factory=Weights)


@dataclass(frozen=True, slots=True)
class Placement:
    """A dish the plan adds to a slot, as a portion of ``session``."""

    date: datetime.date
    mealtime: Mealtime
    recipe_id: str
    session: datetime.date


@dataclass(frozen=True, slots=True)
class Cook:
    """Batches a session cooks on top of what it already has."""

    session: datetime.date
    recipe_id: str
    batches: int


@dataclass(frozen=True, slots=True)
class Plan:
    """A solved plan: what it adds, the archetype per slot, the points."""

    placements: tuple[Placement, ...]
    cooks: tuple[Cook, ...]
    archetypes: tuple[tuple[datetime.date, Mealtime, str], ...]
    points: tuple[tuple[str, float], ...]

    @property
    def total_points(self) -> float:
        """The objective: every term's points summed."""
        return sum(value for _, value in self.points)
