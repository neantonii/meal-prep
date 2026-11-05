"""Week-plan solver — builds the model and maps the answer to ``WeekPlan``.

Solves the cheapest 7-day x 3-meal plan with CP-SAT: breakfasts come from
``BREAKFAST``-category recipes, lunch/dinner from any recipe. Meals are
covered by cooked batches — one integer variable per recipe (0..7; at most
one cook session per recipe per day) — and the objective minimizes full
batch cost, so leftovers are tolerated but charged.
CP-SAT works on integers, so batch costs are scaled to cents first.

Optional convex quadratic terms (``ConvexQuadratic``, in cents) join the
objective through secant cuts (``_add_quadratic``); see
``meal_prep.planner.quadratic``.
"""

from __future__ import annotations

import datetime
from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise

from ortools.sat.python import cp_model
from ortools.sat.python.cp_model import LinearExpr

from meal_prep.enums import Mealtime, RecipeCategory
from meal_prep.models.recipe import Recipe
from meal_prep.planner.plan import (
    DAY_NAMES,
    DailyPlannedMeal,
    HorizonPlan,
    KcalGoal,
    MealSlot,
    MealTemplate,
    PlannedBatch,
    PlannedMeal,
    Role,
    SessionPlan,
    SlotPick,
    WeekPlan,
)
from meal_prep.planner.quadratic import ConvexQuadratic, square_breakpoints

_CENTS = 100
# A batch is a cook session: at most one per recipe per day, so 7 is a safe
# upper bound that never cuts a feasible solution.
_MAX_BATCHES = 7


@dataclass(eq=False)
class _PlannedMeal:
    """One solvable meal: a boolean per candidate recipe.

    Build-scratch only — it holds live solver variables, so it never
    leaves this module. ``eq=False`` because ``IntVar.__eq__`` builds a
    solver expression instead of comparing. Parallel lists stay aligned:
    ``recipes[i]`` is selected by ``is_selected[i]``.
    """

    recipes: list[Recipe]
    is_selected: list[cp_model.IntVar]


@dataclass(eq=False)
class _PlannedDay:
    """One solvable day: a named meal per breakfast/lunch/dinner."""

    day: str
    breakfast: _PlannedMeal
    lunch: _PlannedMeal
    dinner: _PlannedMeal


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
    most ``max_cuts`` secant cuts ``t >= (p + r)·x - p·r`` (``p``, ``r`` neighbouring
    breakpoints). The caller adds
    the returned ``objective`` to the single ``minimize`` call.
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


def plan_week(
    recipes: Sequence[Recipe], *, daily_kcal: ConvexQuadratic | None = None
) -> WeekPlan:
    """Solve the cheapest 7-day x 3-meal plan over ``recipes``.

    ``daily_kcal`` adds a convex penalty (in cents) on each day's kcal,
    e.g. ``ConvexQuadratic.deviation(2100, weight)`` to pull every day
    toward a target. Per-serving kcal are rounded to whole kcal.
    """
    meals = list(recipes)
    if not meals:
        raise ValueError("plan_week needs at least one recipe.")
    breakfasts = [r for r in meals if r.category is RecipeCategory.BREAKFAST]
    if not breakfasts:
        raise ValueError("plan_week needs at least one breakfast recipe.")
    model = cp_model.CpModel()
    week: list[_PlannedDay] = []
    for day in DAY_NAMES:
        breakfast = _new_planned_meal(model, day, "Breakfast", breakfasts)
        lunch = _new_planned_meal(model, day, "Lunch", meals)
        dinner = _new_planned_meal(model, day, "Dinner", meals)
        week.append(
            _PlannedDay(day=day, breakfast=breakfast, lunch=lunch, dinner=dinner)
        )

    for planned_day in week:
        model.add_exactly_one(planned_day.breakfast.is_selected)
        model.add_exactly_one(planned_day.lunch.is_selected)
        model.add_exactly_one(planned_day.dinner.is_selected)

    batches: dict[str, cp_model.IntVar] = {}
    batch_costs_cents: dict[str, int] = {}
    for recipe in meals:
        batches[recipe.id] = model.new_int_var(0, _MAX_BATCHES, f"batches_{recipe.id}")
        batch_costs_cents[recipe.id] = round(recipe.total_cost * _CENTS)

    for recipe in meals:
        uses = [
            var
            for planned_day in week
            for planned_meal in (
                planned_day.breakfast,
                planned_day.lunch,
                planned_day.dinner,
            )
            for candidate, var in zip(
                planned_meal.recipes, planned_meal.is_selected, strict=True
            )
            if candidate.id == recipe.id
        ]
        model.add(sum(uses) <= batches[recipe.id] * round(recipe.servings))

    objective: list[LinearExpr] = [
        batch_costs_cents[recipe.id] * batches[recipe.id] for recipe in meals
    ]
    if daily_kcal is not None:
        objective.extend(
            _add_daily_kcal(model, planned_day, daily_kcal).objective
            for planned_day in week
        )
    model.minimize(LinearExpr.sum(objective))

    solver = cp_model.CpSolver()
    solver.parameters.random_seed = 1
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(
            f"Week-menu solve failed (status={solver.status_name(status)})."
        )

    days: list[DailyPlannedMeal] = []
    for planned_day in week:
        days.append(
            DailyPlannedMeal(
                day=planned_day.day,
                breakfast=_picked_meal(solver, planned_day.breakfast),
                lunch=_picked_meal(solver, planned_day.lunch),
                dinner=_picked_meal(solver, planned_day.dinner),
            )
        )
    prep: list[PlannedBatch] = []
    for recipe in sorted(meals, key=lambda meal: meal.id):
        cooked = solver.value(batches[recipe.id])
        if cooked == 0:
            continue
        used = sum(
            1
            for day in days
            for meal in (day.breakfast, day.lunch, day.dinner)
            if meal.recipe_id == recipe.id
        )
        prep.append(
            PlannedBatch(
                recipe_id=recipe.id,
                title=recipe.title,
                batches=cooked,
                servings=round(recipe.servings),
                portions_used=used,
                cost=recipe.total_cost * cooked,
            )
        )
    return WeekPlan(days=tuple(days), prep=tuple(prep))


def _add_daily_kcal(
    model: cp_model.CpModel, planned_day: _PlannedDay, q: ConvexQuadratic
) -> _QuadraticTerm:
    """Cut ``q`` over the day's kcal; bounds from the cheapest/richest picks."""
    kcal: list[LinearExpr] = []
    lo = hi = 0
    for planned_meal in (planned_day.breakfast, planned_day.lunch, planned_day.dinner):
        options = [_kcal(recipe) for recipe in planned_meal.recipes]
        kcal.extend(
            option * var
            for option, var in zip(options, planned_meal.is_selected, strict=True)
        )
        lo += min(options)
        hi += max(options)
    return _add_quadratic(
        model, LinearExpr.sum(kcal), lo, hi, q, name=f"kcal_{planned_day.day}"
    )


def _kcal(recipe: Recipe) -> int:
    """Per-serving kcal as the integer CP-SAT needs."""
    return round(recipe.per_serving_macros.calories_kcal)


def _new_planned_meal(
    model: cp_model.CpModel, day: str, meal_slot: str, meals: list[Recipe]
) -> _PlannedMeal:
    """Create one solvable meal with a boolean per candidate recipe."""
    candidates: list[Recipe] = []
    is_selected: list[cp_model.IntVar] = []
    for recipe in meals:
        candidates.append(recipe)
        is_selected.append(model.new_bool_var(f"x_{day}_{meal_slot}_{recipe.id}"))
    return _PlannedMeal(
        recipes=candidates,
        is_selected=is_selected,
    )


def _picked_meal(solver: cp_model.CpSolver, planned_meal: _PlannedMeal) -> PlannedMeal:
    """Return the selected recipe; exactly-one guarantees a hit."""
    for recipe, var in zip(planned_meal.recipes, planned_meal.is_selected, strict=True):
        if solver.boolean_value(var):
            return PlannedMeal(
                recipe_id=recipe.id,
                title=recipe.title,
                cost=recipe.cost_per_portion,
                macros=recipe.per_serving_macros,
            )
    raise RuntimeError("No meal selected; exactly-one constraint violated.")


def plan_horizon(
    recipes: Sequence[Recipe],
    slots: Sequence[MealSlot],
    *,
    goal: KcalGoal | None,
    known_kcal: Mapping[datetime.date, float],
    truncated: Collection[datetime.date] = (),
    templates: Mapping[Mealtime, MealTemplate] | None = None,
    time_limit_s: float = 30.0,
    gap_kcal2: float = 1000.0,
    max_cuts: int = 40,
) -> HorizonPlan:
    """Fill ``slots`` (every meal of whole days, any number of sessions).

    No meal rules yet: any recipe in any slot, at most once per slot, slots
    may stay empty. The objective is kcal only (``goal``): a daily term on
    every horizon day and a rolling term on every window whose days are all
    known. ``known_kcal`` holds kcal already eaten or planned outside
    ``slots``: past days, and horizon days' meals that are not slots.
    Batches are the fewest whole batches per session and recipe; nothing
    charges for them yet, so ``truncated`` sessions only get flagged.
    """
    meals = list(recipes)
    model = cp_model.CpModel()
    planned: list[tuple[MealSlot, _PlannedMeal]] = []
    for slot in slots:
        template = None if templates is None else templates.get(slot.mealtime)
        if template is None:
            planned_meal = _new_planned_meal(
                model, slot.date.isoformat(), slot.mealtime.value, meals
            )
        else:
            planned_meal = _templated_meal(model, slot, meals, template)
        planned.append((slot, planned_meal))

    horizon = sorted({slot.date for slot in slots})
    day_kcal: dict[datetime.date, LinearExpr] = {}
    for day in horizon:
        terms = [
            _kcal_units(recipe) * var
            for slot, planned_meal in planned
            if slot.date == day
            for recipe, var in zip(
                planned_meal.recipes, planned_meal.is_selected, strict=True
            )
        ]
        day_kcal[day] = LinearExpr.sum(terms) + _units(known_kcal.get(day, 0.0))

    objective: list[LinearExpr] = []
    if goal is not None:
        _add_kcal_terms(model, objective, goal, horizon, day_kcal, known_kcal, max_cuts)
    model.minimize(LinearExpr.sum(objective))

    solver = cp_model.CpSolver()
    solver.parameters.random_seed = 1
    solver.parameters.max_time_in_seconds = time_limit_s
    # Matching kcal sums is a subset-sum search: proving the last few kcal²
    # costs far more time than it changes the plan. The gap is absolute
    # (logged days make most of the penalty fixed, so a relative one
    # misleads); 1000 kcal² is one day about 32 kcal off.
    solver.parameters.absolute_gap_limit = gap_kcal2 / _KCAL_UNIT**2
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(
            f"Horizon solve failed (status={solver.status_name(status)})."
        )

    picks = [
        SlotPick(
            slot=slot,
            meal=PlannedMeal(
                recipe_id=recipe.id,
                title=recipe.title,
                cost=recipe.cost_per_portion,
                macros=recipe.per_serving_macros,
            ),
        )
        for slot, planned_meal in planned
        for recipe, var in zip(
            planned_meal.recipes, planned_meal.is_selected, strict=True
        )
        if solver.boolean_value(var)
    ]
    by_id = {recipe.id: recipe for recipe in meals}
    sessions: list[SessionPlan] = []
    for session in sorted({slot.session for slot in slots}):
        session_picks = tuple(p for p in picks if p.slot.session == session)
        uses = Counter(p.meal.recipe_id for p in session_picks)
        prep = []
        for recipe_id in sorted(uses):
            recipe = by_id[recipe_id]
            servings = round(recipe.servings)
            cooked = -(-uses[recipe_id] // servings)
            prep.append(
                PlannedBatch(
                    recipe_id=recipe_id,
                    title=recipe.title,
                    batches=cooked,
                    servings=servings,
                    portions_used=uses[recipe_id],
                    cost=recipe.total_cost * cooked,
                )
            )
        sessions.append(
            SessionPlan(
                session=session,
                truncated=session in truncated,
                picks=session_picks,
                prep=tuple(prep),
            )
        )
    kcal_by_day = tuple(
        (
            day,
            known_kcal.get(day, 0.0)
            + sum(p.meal.macros.calories_kcal for p in picks if p.slot.date == day),
        )
        for day in horizon
    )
    return HorizonPlan(
        sessions=tuple(sessions),
        day_kcal=kcal_by_day,
        objective=solver.objective_value * _KCAL_UNIT**2,
        bound=solver.best_objective_bound * _KCAL_UNIT**2,
        seconds=solver.wall_time,
    )


# The horizon model counts kcal in steps of this many kcal: smaller numbers
# make matching sums far easier to find, at most 5 kcal off per recipe.
_KCAL_UNIT = 10


def _units(kcal: float) -> int:
    """``kcal`` in model units (steps of ``_KCAL_UNIT``)."""
    return round(kcal / _KCAL_UNIT)


def _kcal_units(recipe: Recipe) -> int:
    """Per-serving kcal in model units."""
    return _units(recipe.per_serving_macros.calories_kcal)


def _add_kcal_terms(
    model: cp_model.CpModel,
    objective: list[LinearExpr],
    goal: KcalGoal,
    horizon: list[datetime.date],
    day_kcal: Mapping[datetime.date, LinearExpr],
    known_kcal: Mapping[datetime.date, float],
    max_cuts: int,
) -> None:
    """Daily and rolling-window kcal terms (in model units) into ``objective``."""
    daily = ConvexQuadratic.deviation(_units(goal.target), 1.0)
    for day in horizon:
        term = _add_quadratic(
            model,
            day_kcal[day],
            _units(goal.lo),
            _units(goal.hi),
            daily,
            name=f"day_{day}",
            max_cuts=max_cuts,
        )
        objective.append(term.objective)
    if goal.payback > 0:
        rolling = ConvexQuadratic.deviation(
            goal.window * _units(goal.target), goal.window_weight
        )
        for day in horizon:
            window = [
                day - datetime.timedelta(days=back) for back in range(goal.window)
            ]
            if not all(d in day_kcal or d in known_kcal for d in window):
                continue  # a day with nothing known: no window
            total = LinearExpr.sum(
                [
                    day_kcal[d] if d in day_kcal else _units(known_kcal[d])
                    for d in window
                ]
            )
            term = _add_quadratic(
                model,
                total,
                goal.window * _units(goal.lo),
                goal.window * _units(goal.hi),
                rolling,
                name=f"window_{day}",
                max_cuts=max_cuts,
            )
            objective.append(term.objective)


def _templated_meal(
    model: cp_model.CpModel, slot: MealSlot, meals: list[Recipe], template: MealTemplate
) -> _PlannedMeal:
    """A slot restricted to ``template``: its candidates and their rules."""
    tag = f"{slot.date.isoformat()}_{slot.mealtime.value}"
    preset_ids = set().union(*template.presets) if template.presets else set()
    role_of: dict[str, Role] = {}
    for recipe in meals:
        roles = [r for r in template.roles if r.accepts(recipe.id, recipe.category)]
        if len(roles) > 1:
            raise ValueError(f"{recipe.id} fits several roles: {roles}")
        if roles:
            role_of[recipe.id] = roles[0]
    candidates = [
        recipe
        for recipe in meals
        if recipe.id in role_of
        or recipe.id in preset_ids
        or (
            template.extras is not None
            and template.extras.accepts(recipe.id, recipe.category)
        )
    ]
    is_selected = [model.new_bool_var(f"x_{tag}_{r.id}") for r in candidates]
    var_of = {r.id: v for r, v in zip(candidates, is_selected, strict=True)}
    for role in template.roles:
        members = [var_of[rid] for rid, r in role_of.items() if r is role]
        if not members:
            raise ValueError(f"No recipe can fill role '{role.name}' at {tag}.")
        model.add_exactly_one(members)
    if template.presets:
        missing = preset_ids - var_of.keys()
        if missing:
            raise ValueError(f"Unknown preset recipes: {sorted(missing)}")
        chosen = [
            model.new_bool_var(f"preset_{tag}_{k}")
            for k in range(len(template.presets))
        ]
        model.add_exactly_one(chosen)
        for recipe_id in preset_ids:
            model.add(
                var_of[recipe_id]
                == LinearExpr.sum(
                    [
                        c
                        for c, p in zip(chosen, template.presets, strict=True)
                        if recipe_id in p
                    ]
                )
            )
    return _PlannedMeal(recipes=candidates, is_selected=is_selected)
