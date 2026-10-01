"""Week-plan solver — builds the model and maps the answer to ``WeekPlan``.

Solves the cheapest 7-day x 3-meal plan with CP-SAT: breakfasts come from
``BREAKFAST``-category recipes, lunch/dinner from any recipe. Meals are
covered by cooked batches — one integer variable per recipe (0..7; no recipe
repeats within a day, so 7 uses is the ceiling) — and the objective minimizes
full batch cost, so leftovers are tolerated but charged.
CP-SAT works on integers, so batch costs are scaled to cents first.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ortools.sat.python import cp_model

from meal_prep.enums import RecipeCategory
from meal_prep.models.recipe import Recipe
from meal_prep.planner.plan import (
    DAY_NAMES,
    DailyPlannedMeal,
    PlannedBatch,
    PlannedMeal,
    WeekPlan,
)

_CENTS = 100
_MAX_BATCHES = 7


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
        day_meals = (
            planned_day.breakfast,
            planned_day.lunch,
            planned_day.dinner,
        )
        for planned_meal in day_meals:
            model.add_exactly_one(planned_meal.is_selected)
        for recipe in meals:
            model.add(
                sum(
                    var
                    for planned_meal in day_meals
                    for candidate, var in zip(
                        planned_meal.recipes, planned_meal.is_selected, strict=True
                    )
                    if candidate.id == recipe.id
                )
                <= 1
            )

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

    model.minimize(
        sum(batch_costs_cents[recipe.id] * batches[recipe.id] for recipe in meals)
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
