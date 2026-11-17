"""The planner's solver: builds the CP-SAT model and maps the answer to a
``Plan`` (``docs/planner.md``).

Every slot holds what its template allows (exactly one option, its roles
filled by one recipe each, plus optional extras). A recipe is eaten at most
once a day. Each session cooks whole batches of every recipe it feeds:
``uses <= batches * servings``. Soft terms, in points: portions cooked but
not eaten in the plan (leftovers; not charged for sessions the horizon cuts
off) and recipes eaten on two days in a row.

Convex quadratic objective terms (``ConvexQuadratic``) are added through
secant cuts by ``_add_quadratic``; see ``meal_prep.planner.quadratic``.
"""

from __future__ import annotations

import datetime
from collections import defaultdict
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise

from ortools.sat.python import cp_model
from ortools.sat.python.cp_model import LinearExpr

from meal_prep.enums import Mealtime
from meal_prep.models.recipe import Recipe
from meal_prep.planner.plan import (
    MealSlot,
    MealTemplate,
    Plan,
    PlannedBatch,
    SlotPick,
    Weights,
)
from meal_prep.planner.quadratic import ConvexQuadratic, square_breakpoints

_ONE_DAY = datetime.timedelta(days=1)


class NoPlanError(RuntimeError):
    """The rules leave no possible plan (or the solver found none in time)."""


def plan(
    recipes: Sequence[Recipe],
    slots: Sequence[MealSlot],
    templates: Mapping[Mealtime, MealTemplate],
    *,
    eaten: Mapping[datetime.date, Collection[str]] | None = None,
    truncated: Collection[datetime.date] = (),
    weights: Weights | None = None,
    time_limit_s: float = 10.0,
) -> Plan:
    """Fill ``slots`` following ``templates``.

    ``eaten``: the recipes already on each day outside ``slots`` (meals
    placed by hand, accepted meals, the day before the first slot). They
    count for the once-a-day rule and for repeats. ``truncated``: sessions
    whose cycle runs past the horizon; their leftovers are not charged.
    """
    weights = weights or Weights()
    eaten = eaten or {}
    by_id = {recipe.id: recipe for recipe in recipes}
    model = cp_model.CpModel()

    # x[slot index][recipe id]: the recipe is in that slot.
    x: list[dict[str, cp_model.IntVar]] = []
    for index, slot in enumerate(slots):
        template = templates.get(slot.mealtime)
        if template is None:
            raise ValueError(f"No template for {slot.mealtime.value}")
        x.append(_add_slot(model, index, slot, template, recipes))

    # Once a day, counting what is already there.
    per_day: dict[datetime.date, dict[str, list[cp_model.IntVar]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for slot, chosen in zip(slots, x, strict=True):
        for recipe_id, var in chosen.items():
            per_day[slot.date][recipe_id].append(var)
    for day, uses in per_day.items():
        already = set(eaten.get(day, ()))
        for recipe_id, vars_ in uses.items():
            model.add(LinearExpr.sum(vars_) <= (0 if recipe_id in already else 1))

    # Next-day repeats: a recipe on day d and d + 1, at least one of them
    # planned (a repeat between two fixed days is not the plan's doing).
    def used(day: datetime.date, recipe_id: str) -> LinearExpr | int:
        if recipe_id in set(eaten.get(day, ())):
            return 1
        vars_ = per_day.get(day, {}).get(recipe_id, [])
        return LinearExpr.sum(vars_) if vars_ else 0

    repeats: list[cp_model.IntVar] = []
    planned_days = set(per_day)
    pairs = sorted(
        {(d - _ONE_DAY, d) for d in planned_days}
        | {(d, d + _ONE_DAY) for d in planned_days}
    )
    for first, second in pairs:
        candidates = set(per_day.get(first, {})) | set(per_day.get(second, {}))
        for recipe_id in sorted(candidates):
            a, b = used(first, recipe_id), used(second, recipe_id)
            fixed = [v for v in (a, b) if isinstance(v, int)]
            if len(fixed) == 2 or 0 in fixed:
                continue  # both fixed, or one side can never hold it
            flag = model.new_bool_var(f"repeat_{recipe_id}_{first}")
            model.add(flag >= a + b - 1)
            repeats.append(flag)

    # Batches per session and recipe; leftovers charged unless truncated.
    uses_by_batch: dict[tuple[datetime.date, str], list[cp_model.IntVar]] = defaultdict(
        list
    )
    for slot, chosen in zip(slots, x, strict=True):
        for recipe_id, var in chosen.items():
            uses_by_batch[(slot.session, recipe_id)].append(var)
    batch_vars: dict[tuple[datetime.date, str], cp_model.IntVar] = {}
    leftovers: list[LinearExpr] = []
    for (session, recipe_id), vars_ in uses_by_batch.items():
        if session in truncated:
            continue
        servings = _whole(by_id[recipe_id])
        batches = model.new_int_var(0, len(vars_), f"batches_{session}_{recipe_id}")
        model.add(LinearExpr.sum(vars_) <= batches * servings)
        batch_vars[(session, recipe_id)] = batches
        leftovers.append(batches * servings - LinearExpr.sum(vars_))

    model.minimize(
        weights.leftover * LinearExpr.sum(leftovers)
        + weights.next_day_repeat * LinearExpr.sum(repeats)
    )

    solver = cp_model.CpSolver()
    solver.parameters.random_seed = 1
    solver.parameters.num_workers = 1  # same inputs, same plan
    solver.parameters.max_time_in_seconds = time_limit_s
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise NoPlanError(
            f"No plan fits the meal templates (solver: {solver.status_name(status)})"
        )

    picks = tuple(
        SlotPick(slot=slot, recipe_id=recipe_id)
        for slot, chosen in zip(slots, x, strict=True)
        for recipe_id, var in chosen.items()
        if solver.boolean_value(var)
    )
    used_count: dict[tuple[datetime.date, str], int] = defaultdict(int)
    for pick in picks:
        used_count[(pick.slot.session, pick.recipe_id)] += 1
    planned_batches = []
    for (session, recipe_id), count in sorted(used_count.items()):
        servings = _whole(by_id[recipe_id])
        batch_var = batch_vars.get((session, recipe_id))
        cooked = (
            solver.value(batch_var)
            if batch_var is not None
            else -(-count // servings)  # truncated: just enough batches
        )
        planned_batches.append(
            PlannedBatch(
                session=session,
                recipe_id=recipe_id,
                batches=cooked,
                servings=servings,
                used=count,
            )
        )
    leftover_points = weights.leftover * sum(
        b.leftover for b in planned_batches if b.session not in truncated
    )
    repeat_points = weights.next_day_repeat * sum(
        solver.value(flag) for flag in repeats
    )
    return Plan(
        picks=picks,
        batches=tuple(planned_batches),
        points=(("leftovers", leftover_points), ("next-day repeats", repeat_points)),
    )


def _add_slot(
    model: cp_model.CpModel,
    index: int,
    slot: MealSlot,
    template: MealTemplate,
    recipes: Sequence[Recipe],
) -> dict[str, cp_model.IntVar]:
    """The slot's candidate recipes and its template's rules."""
    tag = f"{slot.date}_{slot.mealtime.value}"
    options = []
    for option in template.options:
        members = [
            [r for r in recipes if role.accepts(r.id, r.category)]
            for role in option.roles
        ]
        if all(members):  # an option a missing recipe breaks is left out
            options.append((option, members))
    if not options:
        raise NoPlanError(f"No recipe fits any option for {tag}")
    # recipe id -> the options it fills a role in (a shared recipe, such as
    # the coffee of two breakfasts, may be in several; twice in one, never)
    in_options: dict[str, list[int]] = defaultdict(list)
    for k, (_, members) in enumerate(options):
        ids = [r.id for role_members in members for r in role_members]
        for recipe_id in set(ids):
            if ids.count(recipe_id) > 1:
                raise ValueError(
                    f"{recipe_id} fits more than one role of the "
                    f"{slot.mealtime.value} option '{options[k][0].name}'"
                )
            in_options[recipe_id].append(k)
    extras = [
        r
        for r in recipes
        if template.extras is not None
        and r.id not in in_options
        and template.extras.accepts(r.id, r.category)
    ]

    x = {
        recipe.id: model.new_bool_var(f"x{index}_{tag}_{recipe.id}")
        for recipe in recipes
        if recipe.id in in_options or recipe in extras
    }
    chosen = [model.new_bool_var(f"option{index}_{k}") for k in range(len(options))]
    model.add_exactly_one(chosen)
    for k, (_, members) in enumerate(options):
        for role_members in members:
            role_sum = LinearExpr.sum([x[r.id] for r in role_members])
            model.add(role_sum == 1).only_enforce_if(chosen[k])
    # A role recipe only comes with an option that has it.
    for recipe_id, ks in in_options.items():
        model.add(x[recipe_id] <= LinearExpr.sum([chosen[k] for k in ks]))
    return x


def _whole(recipe: Recipe) -> int:
    """Portions per batch; sessions only take whole numbers."""
    if not recipe.servings.is_integer():
        raise ValueError(f"{recipe.title} yields {recipe.servings:g} servings")
    return int(recipe.servings)


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
