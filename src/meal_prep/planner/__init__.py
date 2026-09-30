"""Weekly meal planner — 7 days x 3 meal slots, one recipe per meal.

Consumes enriched ``meal_prep.models.Recipe`` values, solves the cheapest
assignment with CP-SAT (``meal_prep.planner.solver`` owns the OR-Tools
import), and returns the frozen ``WeekPlan`` (``meal_prep.planner.plan``).
``meal_prep.planner.report`` renders the plan to standalone HTML.
"""

from __future__ import annotations

from meal_prep.planner.plan import DailyPlannedMeal, PlannedMeal, WeekPlan
from meal_prep.planner.solver import plan_week

__all__ = ["DailyPlannedMeal", "PlannedMeal", "WeekPlan", "plan_week"]
