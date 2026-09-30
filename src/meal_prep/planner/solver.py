"""Week-plan solver — the only module that imports OR-Tools.

Solves the cheapest 7-day x 3-meal plan (one recipe per meal, any recipe
allowed) with CP-SAT and maps the answer to the frozen ``WeekPlan``.
CP-SAT works on integers, so portion costs are scaled to cents first.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ortools.sat.python import cp_model

from meal_prep.models.recipe import Recipe
from meal_prep.planner.plan import (
    DAY_NAMES,
    DailyPlannedMeal,
    PlannedMeal,
    WeekPlan,
)

_CENTS = 100


@dataclass(eq=False)
class _PlannedMeal:
    """One solvable meal: a boolean per candidate recipe.

    Build-scratch only — it holds live solver variables, so it never
    leaves this module. ``eq=False`` because ``IntVar.__eq__`` builds a
    solver expression instead of comparing. Parallel lists stay aligned:
    ``recipes[i]`` is selected by ``is_selected[i]`` at ``costs_cents[i]``.
    """

    recipes: list[Recipe]
    costs_cents: list[int]
    is_selected: list[cp_model.IntVar]


@dataclass(eq=False)
class _PlannedDay:
    """One solvable day: a named meal per breakfast/lunch/dinner."""

    day: str
    breakfast: _PlannedMeal
    lunch: _PlannedMeal
    dinner: _PlannedMeal


def plan_week(recipes: Sequence[Recipe]) -> WeekPlan:
    """Solve the cheapest 7-day x 3-meal plan over ``recipes``."""
    meals = list(recipes)
    if not meals:
        raise ValueError("plan_week needs at least one recipe.")
    model = cp_model.CpModel()
    week: list[_PlannedDay] = []
    for day in DAY_NAMES:
        breakfast = _new_planned_meal(model, day, "Breakfast", meals)
        lunch = _new_planned_meal(model, day, "Lunch", meals)
        dinner = _new_planned_meal(model, day, "Dinner", meals)
        week.append(
            _PlannedDay(day=day, breakfast=breakfast, lunch=lunch, dinner=dinner)
        )

    for planned_day in week:
        model.add_exactly_one(planned_day.breakfast.is_selected)
        model.add_exactly_one(planned_day.lunch.is_selected)
        model.add_exactly_one(planned_day.dinner.is_selected)

    model.minimize(
        sum(
            cost * var
            for planned_day in week
            for planned_meal in (
                planned_day.breakfast,
                planned_day.lunch,
                planned_day.dinner,
            )
            for cost, var in zip(
                planned_meal.costs_cents, planned_meal.is_selected, strict=True
            )
        )
    )

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
    return WeekPlan(days=tuple(days))


def _new_planned_meal(
    model: cp_model.CpModel, day: str, meal_slot: str, meals: list[Recipe]
) -> _PlannedMeal:
    """Create one solvable meal with a boolean per candidate recipe."""
    candidates: list[Recipe] = []
    costs_cents: list[int] = []
    is_selected: list[cp_model.IntVar] = []
    for recipe in meals:
        candidates.append(recipe)
        costs_cents.append(round(recipe.cost_per_portion * _CENTS))
        is_selected.append(model.new_bool_var(f"x_{day}_{meal_slot}_{recipe.id}"))
    return _PlannedMeal(
        recipes=candidates,
        costs_cents=costs_cents,
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
