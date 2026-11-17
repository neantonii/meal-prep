"""Plan the week ahead (``docs/planner.md``): read the diary into planner
input, solve, and turn the plan into one diary change.

The horizon is ``HORIZON_DAYS`` calendar days from the next session day
(today or later). Every empty slot in it whose session is that day or later
is filled; slots that hold anything stay as they are and count as eaten.
"""

from __future__ import annotations

import datetime
from collections import defaultdict

from meal_prep.dtos.log import RecipeEntryDTO
from meal_prep.enums import Mealtime
from meal_prep.models.library import Library
from meal_prep.planner.plan import MealSlot
from meal_prep.planner.solver import NoPlanError, plan
from meal_prep.planner.templates import STANDARD
from meal_prep.services import prep

HORIZON_DAYS = 7
_ONE_DAY = datetime.timedelta(days=1)


def first_plan_day(today: datetime.date) -> datetime.date:
    """The next preset session day, today included."""
    return prep.default_session_dates(today, today + 6 * _ONE_DAY)[0]


def plan_week_ahead(
    diary: prep.Diary, policy: prep.Policy, library: Library
) -> prep.Change:
    """Fill the empty slots of the week ahead and write them, flagged."""
    start = first_plan_day(policy.today)
    end = start + (HORIZON_DAYS - 1) * _ONE_DAY

    taken: set[tuple[datetime.date, Mealtime]] = set()
    eaten: dict[datetime.date, set[str]] = defaultdict(set)
    for week in diary.weeks.values():
        for logged in week.days:
            if not start - _ONE_DAY <= logged.date <= end:
                continue
            for mealtime in Mealtime:
                found = getattr(logged, mealtime.value) or ()
                if found:
                    taken.add((logged.date, mealtime))
                for entry in found:
                    if isinstance(entry, RecipeEntryDTO):
                        eaten[logged.date].add(entry.recipe)

    slots = []
    day = start
    while day <= end:
        for mealtime in Mealtime:
            session = prep.cycle_day(day, mealtime)
            if session >= start and (day, mealtime) not in taken:
                slots.append(MealSlot(date=day, mealtime=mealtime, session=session))
        day += _ONE_DAY
    if not slots:
        raise prep.RuleError("Nothing to plan: every meal of the week ahead is set")

    truncated = {s.session for s in slots if prep.next_session_day(s.session) > end}
    recipes = [r for r in library.recipes.values() if r.servings.is_integer()]
    try:
        result = plan(recipes, slots, STANDARD, eaten=eaten, truncated=truncated)
    except NoPlanError as e:
        raise prep.RuleError(str(e)) from e

    cooks = [
        prep.PlannedCook(b.session, b.recipe_id, b.batches) for b in result.batches
    ]
    meals = [
        prep.PlannedMeal(p.slot.date, p.slot.mealtime, p.recipe_id, p.slot.session)
        for p in result.picks
    ]
    return prep.apply_plan(diary, policy, library.recipes, cooks, meals)
