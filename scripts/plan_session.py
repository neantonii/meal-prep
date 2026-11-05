"""Plan one prep session's cycle with the optimizer and write it to the diary.

Usage (run from the repo root):
    python scripts/plan_session.py --diary-dir diary --session 2026-11-05

The cycle is every mealtime (snacks included) that belongs to the session day
(``cycle_day``): for a Thursday session, Thu dinner and snacks through Sun lunch. Any
entries already in those slots are removed first (and the session itself
once nothing links to it), so re-running replaces the previous plan. Picks are added as palette drops (auto-link), so the session
is created and its batches derived by the diary's own rules.
"""

from __future__ import annotations

import argparse
import datetime
from collections.abc import Mapping
from pathlib import Path

from meal_prep.enums import Mealtime
from meal_prep.library import load_library
from meal_prep.models.recipe import Recipe
from meal_prep.planner.plan import MealSlot, SessionPlan
from meal_prep.planner.solver import plan_session
from meal_prep.server.store import DiaryStore
from meal_prep.server.weeks import current_week
from meal_prep.services import prep

PLANNED_MEALTIMES = tuple(Mealtime)


def week_of(date: datetime.date) -> str:
    """ISO week id of ``date``, e.g. ``2026-W45``."""
    return current_week(date)


def cycle_slots(session_day: datetime.date) -> list[MealSlot]:
    """The meals a session on ``session_day`` feeds, in eating order."""
    end = prep.next_session_day(session_day)
    slots: list[MealSlot] = []
    day = session_day
    while day <= end:
        for mealtime in PLANNED_MEALTIMES:
            if prep.cycle_day(day, mealtime) == session_day:
                slots.append(MealSlot(date=day, mealtime=mealtime))
        day += datetime.timedelta(days=1)
    return slots


def clear_slots(store: DiaryStore, policy: prep.Policy, slots: list[MealSlot]) -> int:
    """Remove every entry in ``slots``; returns how many went."""
    wanted = {(slot.date, slot.mealtime) for slot in slots}
    removed = 0
    for week in sorted({week_of(slot.date) for slot in slots}):
        dto = store.load().weeks.get(week)
        if dto is None:
            continue
        doomed = [
            entry.id
            for day in dto.days
            for mealtime in PLANNED_MEALTIMES
            if (day.date, mealtime) in wanted
            for entry in getattr(day, mealtime.value) or ()
        ]
        for entry_id in doomed:
            before = store.load()
            store.apply(before, prep.remove_entry(before, policy, week, entry_id))
            removed += 1
    return removed


def drop_unlinked_session(
    store: DiaryStore, policy: prep.Policy, session_day: datetime.date
) -> None:
    """Delete the session on ``session_day`` once nothing links to it.

    From its own day on, a session keeps unlinked portions as a record, so a
    re-plan would otherwise inherit the previous plan's batches as spares.
    """
    diary = store.load()
    for session_id, session in diary.sessions.items():
        if session.date != session_day:
            continue
        if any(
            count
            for (sid, _), count in prep.link_counts(diary.weeks.values()).items()
            if sid == session_id
        ):
            return
        store.apply(diary, prep.delete_session(diary, policy, session_id))


def write_plan(
    store: DiaryStore,
    policy: prep.Policy,
    recipes: Mapping[str, Recipe],
    plan: SessionPlan,
) -> None:
    """Add every pick as an auto-linked entry."""
    for pick in plan.picks:
        before = store.load()
        change, _ = prep.add_entry(
            before,
            policy,
            recipes,
            week_of(pick.slot.date),
            pick.slot.date,
            pick.slot.mealtime,
            recipes[pick.meal.recipe_id],
        )
        store.apply(before, change)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--recipes-dir", type=Path, default=Path("recipes"))
    parser.add_argument("--diary-dir", type=Path, required=True)
    parser.add_argument("--session", type=datetime.date.fromisoformat, required=True)
    parser.add_argument(
        "--today",
        type=datetime.date.fromisoformat,
        default=datetime.date.today(),
        help="Splits Plan from Log, as on the server (default: today)",
    )
    args = parser.parse_args()

    library = load_library(args.data_dir, args.recipes_dir)
    store = DiaryStore(args.diary_dir)
    policy = prep.Policy(today=args.today)

    slots = cycle_slots(args.session)
    removed = clear_slots(store, policy, slots)
    drop_unlinked_session(store, policy, args.session)
    plan = plan_session(list(library.recipes.values()), slots)
    write_plan(store, policy, library.recipes, plan)

    print(f"Session {args.session}: {len(slots)} slots, {removed} old entries removed")
    for pick in plan.picks:
        print(f"  {pick.slot.date:%a} {pick.slot.mealtime.value:9} {pick.meal.title}")
    print("Prep:")
    for batch in plan.prep:
        print(
            f"  {batch.title}: {batch.batches} x {batch.servings} "
            f"({batch.portions_used} used) ${batch.cost:.2f}"
        )
    print(f"Total ${plan.total_cost:.2f}")


if __name__ == "__main__":
    main()
