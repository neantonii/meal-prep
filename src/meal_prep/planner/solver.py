"""The planner's solver: one CP-SAT model over shared variables, an
objective made of named terms (``docs/planner.md``).

Variables: ``x[slot][(recipe, session)]``, how many portions of a recipe
from a session's batch are in a slot (history slots and pinned dishes
included); ``b[(session, recipe)]``, batches; and one archetype choice per
slot. Existing items only fix variables (a pin is a lower bound on ``x``; a
history slot is fixed entirely; a cooked batch is fixed, a planned one
keeps at least its batches). The only hard constraints are the diary's
own: a batch's meals never exceed its portions, and a portion is eaten on
or after its session's date (candidates are only created that way). So
pins can never make the model infeasible.

Each term reads the shared variables and returns weighted parts; the
objective is their sum, and the plan reports the points per term.

Convex quadratic objective terms (``ConvexQuadratic``) are added through
secant cuts by ``_add_quadratic``; see ``meal_prep.planner.quadratic``.
"""

from __future__ import annotations

import datetime
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Protocol

from ortools.sat.python import cp_model
from ortools.sat.python.cp_model import LinearExpr

from meal_prep.enums import Mealtime, RecipeCategory
from meal_prep.models.recipe import Recipe
from meal_prep.planner.plan import (
    TAKEOUT,
    Archetype,
    Batch,
    Cook,
    Placement,
    Plan,
    Problem,
    Slot,
)
from meal_prep.planner.quadratic import ConvexQuadratic, square_breakpoints

_ONE_DAY = datetime.timedelta(days=1)
# What a leftover portion of a session cut off by the horizon costs, as a
# share of a full leftover: enough to keep its batches minimal.
CUT_OFF_SHARE = 0.01

type _Key = tuple[str, datetime.date | None]  # (recipe id, session)
type _Part = tuple[float, LinearExpr | cp_model.IntVar]  # (weight, value)


class NoPlanError(RuntimeError):
    """The solver found no plan (only possible with inconsistent input)."""


@dataclass(eq=False)
class Context:
    """The shared model every term reads. Build-scratch only: it holds live
    solver variables, so it never leaves this module."""

    model: cp_model.CpModel
    problem: Problem
    category: Mapping[str, RecipeCategory | None]
    # (date, mealtime) -> key -> portions in the slot
    x: dict[tuple[datetime.date, Mealtime], dict[_Key, cp_model.IntVar]]
    pinned: dict[tuple[datetime.date, Mealtime], Counter[_Key]]
    planned: set[tuple[datetime.date, Mealtime]]  # horizon slots (not history)
    batches: dict[tuple[datetime.date, str], cp_model.IntVar]
    servings: dict[tuple[datetime.date, str], int]
    existing: dict[tuple[datetime.date, str], int]  # batches already there
    outside: dict[tuple[datetime.date, str], int]
    archetype: dict[tuple[datetime.date, Mealtime], dict[str, cp_model.IntVar]] = field(
        default_factory=dict
    )

    def day_uses(self, day: datetime.date, recipe_id: str) -> list[cp_model.IntVar]:
        """Every variable that puts ``recipe_id`` on ``day``."""
        return [
            var
            for (date, _), keys in self.x.items()
            if date == day
            for (rid, _), var in keys.items()
            if rid == recipe_id
        ]


class Term(Protocol):
    """One part of the objective: weighted values over the shared model."""

    @property
    def name(self) -> str: ...

    def build(self, ctx: Context) -> list[_Part]: ...


def plan(
    recipes: Sequence[Recipe], problem: Problem, *, time_limit_s: float = 10.0
) -> Plan:
    """Solve ``problem``: what to add to each slot, and what to cook."""
    by_id = {recipe.id: recipe for recipe in recipes if recipe.servings.is_integer()}
    ctx = _build(by_id, problem)
    terms: list[Term] = [
        ArchetypeFit(),
        SameDayRepeat(problem.weights.same_day_repeat),
        NextDayRepeat(problem.weights.next_day_repeat),
        Leftovers(problem.weights.leftover),
    ]
    parts = {term.name: term.build(ctx) for term in terms}
    ctx.model.minimize(
        LinearExpr.sum(
            [weight * value for found in parts.values() for weight, value in found]
        )
    )

    solver = cp_model.CpSolver()
    solver.parameters.random_seed = 1
    solver.parameters.num_workers = 1  # same inputs, same plan
    solver.parameters.max_time_in_seconds = time_limit_s
    status = solver.solve(ctx.model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise NoPlanError(f"No plan found (solver: {solver.status_name(status)})")

    placements: list[Placement] = []
    for slot_key in sorted(ctx.planned, key=_slot_order):
        for (recipe_id, session), var in sorted(
            ctx.x[slot_key].items(), key=lambda kv: (kv[0][0], str(kv[0][1]))
        ):
            added = solver.value(var) - ctx.pinned[slot_key][(recipe_id, session)]
            if session is None or added <= 0:
                continue
            date, mealtime = slot_key
            placements.extend(
                Placement(date, mealtime, recipe_id, session) for _ in range(added)
            )
    cooks = [
        Cook(session, recipe_id, solver.value(var) - ctx.existing[(session, recipe_id)])
        for (session, recipe_id), var in sorted(ctx.batches.items())
        if solver.value(var) > ctx.existing[(session, recipe_id)]
    ]
    chosen = tuple(
        (date, mealtime, name)
        for (date, mealtime), options in sorted(
            ctx.archetype.items(), key=lambda kv: _slot_order(kv[0])
        )
        for name, var in options.items()
        if solver.boolean_value(var)
    )
    points = tuple(
        (name, sum(w * solver.value(v) for w, v in found))
        for name, found in parts.items()
    )
    return Plan(
        placements=tuple(placements),
        cooks=tuple(cooks),
        archetypes=chosen,
        points=points,
    )


def _upper(var: cp_model.IntVar) -> int:
    """A variable's upper bound. (Its proto's domain is a repeated field
    where ``[-1]`` does not index from the end.)"""
    domain: list[int] = list(var.proto.domain)
    return domain[-1]


def _slot_order(key: tuple[datetime.date, Mealtime]) -> tuple[datetime.date, int]:
    return key[0], list(Mealtime).index(key[1])


def _build(recipes: Mapping[str, Recipe], problem: Problem) -> Context:
    """The shared variables: dishes per slot (pins as lower bounds, history
    fixed), batches per session and recipe with their portion limit."""
    model = cp_model.CpModel()
    category: dict[str, RecipeCategory | None] = {
        rid: r.category for rid, r in recipes.items()
    }
    pinned: dict[tuple[datetime.date, Mealtime], Counter[_Key]] = defaultdict(Counter)
    for pin in problem.pins:
        pinned[(pin.date, pin.mealtime)][(pin.recipe_id, pin.session)] += 1
        category.setdefault(pin.recipe_id, None)

    existing = {(b.session, b.recipe_id): b for b in problem.batches}
    sessions = set(problem.sessions)
    x: dict[tuple[datetime.date, Mealtime], dict[_Key, cp_model.IntVar]] = {}

    for slot in problem.history:
        key = (slot.date, slot.mealtime)
        x[key] = {
            k: model.new_int_var(n, n, f"h_{slot.date}_{slot.mealtime}_{k[0]}")
            for k, n in pinned[key].items()
        }

    def candidates(slot: Slot) -> set[_Key]:
        """Recipes any archetype of the mealtime takes, from the slot's
        cycle session (cooked there) or from stock of an earlier session
        that is still good (fridge life, or freezable)."""
        found: set[_Key] = set()
        roles = [
            role
            for archetype in problem.archetypes.get(slot.mealtime, ())
            if archetype.plannable
            for role in archetype.roles
        ]
        for rid, recipe in recipes.items():
            if not any(role.accepts(rid, recipe.category) for role in roles):
                continue
            if slot.cycle in sessions:
                found.add((rid, slot.cycle))
            for batch in problem.batches:
                if (
                    batch.recipe_id == rid
                    and batch.unassigned > 0
                    and batch.session <= slot.date
                    and _still_good(batch, slot.date)
                ):
                    found.add((rid, batch.session))
        return found

    for slot in problem.slots:
        key = (slot.date, slot.mealtime)
        wanted = candidates(slot) | set(pinned[key])
        x[key] = {}
        for k in sorted(wanted, key=lambda k: (k[0], str(k[1]))):
            low = pinned[key][k]
            x[key][k] = model.new_int_var(
                low, max(low, 1), f"x_{slot.date}_{slot.mealtime}_{k[0]}_{k[1]}"
            )

    uses: dict[tuple[datetime.date, str], list[cp_model.IntVar]] = defaultdict(list)
    for keys in x.values():
        for (rid, session), var in keys.items():
            if session is not None and rid != TAKEOUT:
                uses[(session, rid)].append(var)
    batches: dict[tuple[datetime.date, str], cp_model.IntVar] = {}
    servings: dict[tuple[datetime.date, str], int] = {}
    already: dict[tuple[datetime.date, str], int] = {}
    outside: dict[tuple[datetime.date, str], int] = {}
    for (session, rid), vars_ in sorted(uses.items()):
        known = existing.get((session, rid))
        if known is not None:
            serving, low = known.servings, known.batches
            high = low if known.fixed else low + len(vars_)
            outside[(session, rid)] = known.outside
        elif rid in recipes:
            serving, low, high = int(recipes[rid].servings), 0, len(vars_)
            outside[(session, rid)] = 0
        else:
            continue  # a pinned meal of a recipe that is gone: no batch to track
        var = model.new_int_var(low, high, f"b_{session}_{rid}")
        model.add(LinearExpr.sum(vars_) + outside[(session, rid)] <= var * serving)
        batches[(session, rid)] = var
        servings[(session, rid)] = serving
        already[(session, rid)] = low
    return Context(
        model=model,
        problem=problem,
        category=category,
        x=x,
        pinned=pinned,
        planned={(s.date, s.mealtime) for s in problem.slots},
        batches=batches,
        servings=servings,
        existing=already,
        outside=outside,
    )


def _still_good(batch: Batch, day: datetime.date) -> bool:
    """Whether an earlier batch's portion can still be eaten on ``day``."""
    if batch.fridge_days is None or batch.freezer_friendly:
        return True
    return (day - batch.session).days <= batch.fridge_days


# ---------------------------------------------------------------------------
# Terms
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ArchetypeFit:
    """Each planned slot chooses one archetype and pays for the misfit:
    every role's shortfall and excess, and each pinned dish no role takes.
    The plan only adds dishes the chosen archetype takes (pins are never
    limited). An archetype the planner may not choose itself (eat out) is
    offered only where a pinned dish fits it."""

    name: str = "archetype fit"

    def build(self, ctx: Context) -> list[_Part]:
        parts: list[_Part] = []
        model = ctx.model
        for slot in ctx.problem.slots:
            key = (slot.date, slot.mealtime)
            dishes = ctx.x[key]
            pinned = ctx.pinned[key]
            offered = [
                a
                for a in ctx.problem.archetypes.get(slot.mealtime, ())
                if a.plannable or _fits_a_pin(a, ctx, key)
            ]
            if not offered:
                continue
            chosen = {
                a.name: model.new_bool_var(f"a_{slot.date}_{slot.mealtime}_{a.name}")
                for a in offered
            }
            model.add_exactly_one(chosen.values())
            ctx.archetype[key] = chosen

            def fits(rid: str, archetype: Archetype) -> bool:
                return any(
                    role.accepts(rid, ctx.category.get(rid)) for role in archetype.roles
                )

            # What the plan adds must fit the chosen archetype.
            for k, var in dishes.items():
                takers = [chosen[a.name] for a in offered if fits(k[0], a)]
                room = _upper(var) - pinned[k]
                if room <= 0:
                    continue
                if takers:
                    model.add(var - pinned[k] <= room * LinearExpr.sum(takers))
                else:
                    model.add(var == pinned[k])

            for archetype in offered:
                pick = chosen[archetype.name]
                tag = f"{slot.date}_{slot.mealtime}_{archetype.name}"
                _check_pools(archetype, dishes, ctx)
                for role in archetype.roles:
                    members = {
                        k: var
                        for k, var in dishes.items()
                        if role.accepts(k[0], ctx.category.get(k[0]))
                    }
                    low, high = role.count
                    already = sum(pinned[k] for k in members)
                    added = [var - pinned[k] for k, var in members.items()]
                    # The plan never overfills a role: what it adds under this
                    # archetype fits in the room the pins leave. (A dish that
                    # another archetype also takes may come in under that one.)
                    shared = [
                        (_upper(var) - pinned[k]) * chosen[b.name]
                        for k, var in members.items()
                        for b in offered
                        if b is not archetype and fits(k[0], b)
                    ]
                    if added:
                        model.add(
                            LinearExpr.sum(added)
                            <= max(0, high - already) * pick + LinearExpr.sum(shared)
                        )
                    if low > already:
                        short = model.new_int_var(0, low, f"short_{tag}_{role.name}")
                        filled = LinearExpr.sum(added) if added else 0
                        model.add(short >= (low - already) * pick - filled)
                        parts.append((role.missing, short))
                    if already > high:  # only pins can overfill a role
                        parts.append((role.extra * (already - high), pick))
                strays = sum(n for k, n in pinned.items() if not fits(k[0], archetype))
                if strays:
                    parts.append((archetype.unknown * strays, pick))
                if archetype.base_cost:
                    parts.append((archetype.base_cost, pick))
        return parts


def _fits_a_pin(
    archetype: Archetype, ctx: Context, key: tuple[datetime.date, Mealtime]
) -> bool:
    return any(
        role.accepts(rid, ctx.category.get(rid))
        for (rid, _) in ctx.pinned[key]
        for role in archetype.roles
    )


def _check_pools(
    archetype: Archetype, dishes: Mapping[_Key, object], ctx: Context
) -> None:
    for rid in {k[0] for k in dishes}:
        roles = [r for r in archetype.roles if r.accepts(rid, ctx.category.get(rid))]
        if len(roles) > 1:
            raise ValueError(
                f"{rid} is in two roles of archetype '{archetype.name}': "
                f"{', '.join(r.name for r in roles)}"
            )


@dataclass(frozen=True)
class SameDayRepeat:
    """Points per extra use of a recipe in one planned day."""

    weight: float
    name: str = "same-day repeats"

    def build(self, ctx: Context) -> list[_Part]:
        parts: list[_Part] = []
        for day in sorted({d for d, _ in ctx.planned}):
            recipe_ids = {
                rid
                for (date, _), keys in ctx.x.items()
                if date == day
                for (rid, _) in keys
                if rid != TAKEOUT
            }
            for rid in sorted(recipe_ids):
                uses = ctx.day_uses(day, rid)
                if len(uses) < 2 and all(_upper(u) <= 1 for u in uses):
                    continue
                extra = ctx.model.new_int_var(0, 2 * len(uses), f"twice_{day}_{rid}")
                ctx.model.add(extra >= LinearExpr.sum(uses) - 1)
                parts.append((self.weight, extra))
        return parts


@dataclass(frozen=True)
class NextDayRepeat:
    """Points per recipe eaten on two days in a row (history included; a
    pair of two history days is left out, nothing can change it)."""

    weight: float
    name: str = "next-day repeats"

    def build(self, ctx: Context) -> list[_Part]:
        model = ctx.model
        days = sorted({date for date, _ in ctx.x})
        planned_days = {d for d, _ in ctx.planned}
        eaten: dict[tuple[datetime.date, str], cp_model.IntVar] = {}

        def on(day: datetime.date, rid: str) -> cp_model.IntVar:
            if (day, rid) not in eaten:
                uses = ctx.day_uses(day, rid)
                flag = model.new_bool_var(f"on_{day}_{rid}")
                for use in uses:  # eaten that day as soon as one use is there
                    model.add(flag * _upper(use) >= use)
                model.add(flag <= LinearExpr.sum(uses))
                eaten[(day, rid)] = flag
            return eaten[(day, rid)]

        parts: list[_Part] = []
        for first, second in pairwise(days):
            if second - first != _ONE_DAY:
                continue
            if first not in planned_days and second not in planned_days:
                continue
            both = {
                rid
                for (date, _), keys in ctx.x.items()
                if date in (first, second)
                for (rid, _) in keys
                if rid != TAKEOUT
            }
            for rid in sorted(both):
                if not ctx.day_uses(first, rid) or not ctx.day_uses(second, rid):
                    continue
                flag = model.new_bool_var(f"repeat_{first}_{rid}")
                model.add(flag >= on(first, rid) + on(second, rid) - 1)
                parts.append((self.weight, flag))
        return parts


@dataclass(frozen=True)
class Leftovers:
    """Points per portion of a batch the plan leaves uneaten (Unassigned),
    for every batch it touches, manual ones included. A session the horizon
    cuts off pays a token ``CUT_OFF_SHARE`` of it: its cycle continues past
    the horizon, so its leftovers may still be eaten, but it must not cook
    more than its planned meals need."""

    weight: float
    name: str = "leftovers"

    def build(self, ctx: Context) -> list[_Part]:
        parts: list[_Part] = []
        for (session, rid), var in ctx.batches.items():
            weight = self.weight
            if session in ctx.problem.truncated:
                weight *= CUT_OFF_SHARE
            used = [
                v
                for keys in ctx.x.values()
                for (k_rid, k_session), v in keys.items()
                if k_rid == rid and k_session == session
            ]
            left = (
                var * ctx.servings[(session, rid)]
                - LinearExpr.sum(used)
                - ctx.outside[(session, rid)]
            )
            parts.append((weight, left))
        return parts


@dataclass(eq=False)
class _QuadraticTerm:
    """One cut quadratic: what ``_add_quadratic`` built for ``q(x)``.

    ``t >= x²`` via secants at ``breakpoints`` (exact there, a slight
    overestimate between them); ``objective`` is ``c·t + b·x + d``. Report
    ``q(value of x)``, not the cut estimate.
    """

    x: LinearExpr
    t: cp_model.IntVar
    objective: LinearExpr
    q: ConvexQuadratic
    breakpoints: tuple[int, ...]


def _add_quadratic(
    model: cp_model.CpModel,
    x: LinearExpr,
    lo: int,
    hi: int,
    q: ConvexQuadratic,
    *,
    name: str,
    max_cuts: int = 100,
) -> _QuadraticTerm:
    """Add ``q(x)`` for an integer expression ``x`` known to lie in ``[lo, hi]``.

    Adds ``lo <= x <= hi`` (past the outer breakpoints a secant would
    underestimate ``x²``, so the bounds must hold), a variable ``t`` and at
    most ``max_cuts`` secant cuts ``t >= (p + r)·x - p·r`` for neighbouring
    breakpoints ``p``, ``r``. The caller adds the returned ``objective`` to
    its single ``minimize`` call.
    """
    model.add(x >= lo)
    model.add(x <= hi)
    squares = (lo * lo, hi * hi)
    t_min = 0 if lo <= 0 <= hi else min(squares)
    t = model.new_int_var(t_min, max(squares), f"{name}_sq")
    breakpoints = square_breakpoints(lo, hi, q.vertex, max_cuts)
    if len(breakpoints) == 1:
        model.add(t == lo * lo)
    for left, right in pairwise(breakpoints):
        model.add(t >= (left + right) * x - left * right)
    return _QuadraticTerm(
        x=x,
        t=t,
        objective=q.c * t + q.b * x + q.d,
        q=q,
        breakpoints=breakpoints,
    )
