"""Plan the week ahead (``docs/planner.md``): read the diary into the
planner's problem, solve, and write the plan as one diary change.

The horizon is ``HORIZON_DAYS`` calendar days from the next session day
(today included). Every slot of it whose cycle session is that day or
later is planned; everything already in the diary is a pin: meals on days
(manual, accepted, takeout, an earlier plan's), the batches sessions
already have, and their unassigned portions as stock the plan may use.
The day before the horizon, and the start day's meals from the previous
cycle, are history: fully pinned, they count for repeats.
"""

from __future__ import annotations

import datetime
from collections import Counter

from meal_prep.dtos.log import TakeoutEntryDTO
from meal_prep.enums import Mealtime
from meal_prep.models.library import Library
from meal_prep.planner.plan import TAKEOUT, Batch, Pin, Plan, Problem, Slot
from meal_prep.planner.solver import NoPlanError, plan, score
from meal_prep.services import prep

HORIZON_DAYS = 7
HISTORY_DAYS = 1  # how far back the terms look (next-day repeats)
_ONE_DAY = datetime.timedelta(days=1)


def first_plan_day(today: datetime.date) -> datetime.date:
    """The next preset session day, today included."""
    return prep.default_session_dates(today, today + 6 * _ONE_DAY)[0]


def plan_problem(diary: prep.Diary, policy: prep.Policy, library: Library) -> Problem:
    """The planner's view of the diary for the week ahead."""
    start = first_plan_day(policy.today)
    end = start + (HORIZON_DAYS - 1) * _ONE_DAY
    first = start - HISTORY_DAYS * _ONE_DAY

    slots: list[Slot] = []
    history: list[Slot] = []
    day = first
    while day <= end:
        for mealtime in Mealtime:
            cycle = prep.cycle_day(day, mealtime)
            slot = Slot(date=day, mealtime=mealtime, cycle=cycle)
            (slots if day >= start and cycle >= start else history).append(slot)
        day += _ONE_DAY
    in_model = {(s.date, s.mealtime) for s in (*slots, *history)}

    session_dates = {s.id: s.date for s in diary.sessions.values()}
    pins: list[Pin] = []
    on_days: Counter[tuple[datetime.date, str]] = Counter()  # outside the model
    for week in diary.weeks.values():
        for logged in week.days:
            for mealtime in Mealtime:
                for entry in getattr(logged, mealtime.value) or ():
                    seen = (logged.date, mealtime) in in_model
                    if isinstance(entry, TakeoutEntryDTO):
                        if seen:
                            pins.append(Pin(logged.date, mealtime, TAKEOUT))
                        continue
                    session = (
                        session_dates.get(entry.session) if entry.session else None
                    )
                    if seen:
                        pins.append(Pin(logged.date, mealtime, entry.recipe, session))
                    elif session is not None:
                        on_days[(session, entry.recipe)] += 1

    unassigned = Counter(
        (session_dates[m.session], m.recipe)
        for m in diary.unassigned
        if m.session in session_dates
    )
    binned = Counter(
        (session_dates[m.session], m.recipe)
        for m in diary.bin
        if m.session in session_dates
    )
    batches = [
        Batch(
            session=session.date,
            recipe_id=item.recipe,
            batches=item.batches,
            servings=item.servings,
            outside=on_days[(session.date, item.recipe)]
            + binned[(session.date, item.recipe)],
            unassigned=unassigned[(session.date, item.recipe)],
            fixed=not policy.session_open(session.date),
            fridge_days=item.fridge_days,
            freezer_friendly=item.freezer_friendly,
        )
        for session in diary.sessions.values()
        for item in session.items
    ]

    cookable = {s.cycle for s in slots}
    return Problem(
        slots=tuple(slots),
        history=tuple(history),
        pins=tuple(pins),
        batches=tuple(batches),
        sessions=tuple(sorted(cookable)),
        archetypes=dict(library.archetypes),
        truncated=frozenset(s for s in cookable if prep.next_session_day(s) > end),
    )


def plan_week_ahead(
    diary: prep.Diary, policy: prep.Policy, library: Library
) -> prep.Change:
    """Plan the week ahead and write what it adds, flagged ``planned``."""
    problem = plan_problem(diary, policy, library)
    try:
        result = plan(list(library.recipes.values()), problem)
    except NoPlanError as e:
        raise prep.RuleError(str(e)) from e
    if not result.placements and not result.cooks:
        raise prep.RuleError("Nothing to add: the week ahead is already planned")
    cooks = [prep.PlannedCook(c.session, c.recipe_id, c.batches) for c in result.cooks]
    meals = [
        prep.PlannedMeal(p.date, p.mealtime, p.recipe_id, p.session)
        for p in result.placements
    ]
    return prep.apply_plan(diary, policy, library.recipes, cooks, meals)


def explain_week_ahead(
    diary: prep.Diary, policy: prep.Policy, library: Library
) -> Plan:
    """The bill of the week ahead as it stands (the planner's meals and
    yours alike): points per term and line, each meal's archetype, and any
    broken hard rule. Nothing is changed."""
    problem = plan_problem(diary, policy, library)
    try:
        return score(list(library.recipes.values()), problem)
    except NoPlanError as e:
        raise prep.RuleError(str(e)) from e
