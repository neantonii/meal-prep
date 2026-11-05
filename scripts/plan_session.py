"""Plan one prep session with the optimizer and write it to the diary.

Usage (run from the repo root):
    python scripts/plan_session.py --diary-dir diary --session 2026-11-05

Rolling horizon: every meal of ``--days`` whole days from the session day
is planned (the session's own cycle plus draft cycles of the next sessions),
but only the session's own cycle is written; the drafts are printed.
Entries already in the session's cycle are removed first (and the session
once nothing links to it), so re-running replaces the previous plan. Other
diary entries count as kcal already eaten or planned. Picks are added as
palette drops (auto-link), so the session and its batches come from the
diary's own rules.
"""

from __future__ import annotations

import argparse
import datetime
from collections.abc import Mapping
from pathlib import Path

from meal_prep.enums import Mealtime
from meal_prep.library import load_library
from meal_prep.models.recipe import Recipe
from meal_prep.planner.plan import KcalGoal, MealSlot, SessionPlan
from meal_prep.planner.solver import plan_horizon
from meal_prep.server.store import DiaryStore
from meal_prep.server.weeks import current_week
from meal_prep.services import prep

PLANNED_MEALTIMES = tuple(Mealtime)


def week_of(date: datetime.date) -> str:
    """ISO week id of ``date``, e.g. ``2026-W45``."""
    return current_week(date)


def horizon_slots(session_day: datetime.date, days: int) -> list[MealSlot]:
    """Every meal of ``days`` whole days from ``session_day`` that this or a
    later session feeds (earlier sessions' meals are already settled)."""
    return [
        MealSlot(date=day, mealtime=mealtime, session=cycle)
        for offset in range(days)
        for mealtime in PLANNED_MEALTIMES
        if (
            cycle := prep.cycle_day(
                day := session_day + datetime.timedelta(days=offset), mealtime
            )
        )
        >= session_day
    ]


def known_kcal(
    store: DiaryStore, start: datetime.date, end: datetime.date
) -> dict[datetime.date, float]:
    """Kcal of every diary entry from ``start`` to ``end``, per logged day."""
    totals: dict[datetime.date, float] = {}
    for week in store.load().weeks.values():
        for day in week.days:
            if start <= day.date <= end:
                totals[day.date] = sum(e.calories_kcal for e in day.entries())
    return totals


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
    parser.add_argument("--days", type=int, default=7, help="Horizon length")
    parser.add_argument("--payback", type=float, default=0.5)
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

    goal = KcalGoal(payback=args.payback)
    slots = horizon_slots(args.session, args.days)
    own = [slot for slot in slots if slot.session == args.session]
    removed = clear_slots(store, policy, own)
    drop_unlinked_session(store, policy, args.session)

    end = slots[-1].date
    known = known_kcal(
        store, args.session - datetime.timedelta(days=goal.window - 1), end
    )
    sessions = {slot.session for slot in slots}
    truncated = {s for s in sessions if prep.next_session_day(s) > end}
    plan = plan_horizon(
        list(library.recipes.values()),
        slots,
        goal=goal,
        known_kcal=known,
        truncated=truncated,
    )
    write_plan(store, policy, library.recipes, plan.sessions[0])

    print(
        f"Horizon {args.session}..{end}: {len(slots)} slots, "
        f"{removed} old entries removed; wrote session {args.session}"
    )
    print(
        f"Penalty {plan.objective:.0f} (bound {plan.bound:.0f}), "
        f"solved in {plan.seconds:.1f}s"
    )
    kcal = dict(plan.day_kcal)
    for offset in range(-(goal.window - 1), args.days):
        day = args.session + datetime.timedelta(days=offset)
        total = kcal.get(day, known.get(day))
        if total is None:
            continue
        window = [
            kcal.get(d, known.get(d))
            for d in (day - datetime.timedelta(days=b) for b in range(goal.window))
        ]
        avg = (
            f"{sum(window) / goal.window:7.0f}"  # type: ignore[arg-type]
            if all(v is not None for v in window)
            else "      -"
        )
        tag = "plan" if day in kcal else "log "
        print(f"  {day:%a %d} {tag} {total:6.0f} kcal  {goal.window}-day avg {avg}")
    for session in plan.sessions:
        state = "written" if session.session == args.session else "draft"
        if session.truncated:
            state += ", truncated"
        print(f"Session {session.session:%a %d %b} ({state}):")
        for pick in session.picks:
            print(
                f"    {pick.slot.date:%a} {pick.slot.mealtime.value:9} "
                f"{pick.meal.title} ({pick.meal.macros.calories_kcal:.0f})"
            )


if __name__ == "__main__":
    main()
