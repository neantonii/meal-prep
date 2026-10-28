"""Build the week page the UI shows: 7 days, session cards and totals.

Read-only: turns the loaded diary (``services.prep.Diary``) into the API
shapes, with titles and numbers from the frozen entries and session items.
"""

from __future__ import annotations

import datetime

from meal_prep.models.ingredient import MacrosInfo
from meal_prep.models.library import Library
from meal_prep.models.log import LogEntry
from meal_prep.models.recipe import Recipe
from meal_prep.models.session import PrepSession
from meal_prep.server.api_models import (
    DiaryDay,
    DiaryEntry,
    DiaryMeal,
    DiaryWeek,
    Session,
    SessionItem,
)
from meal_prep.server.weeks import week_dates
from meal_prep.services import prep
from meal_prep.services.logs import prepare_diary_week
from meal_prep.services.sessions import prepare_session


def _totals(cost: float, macros: MacrosInfo) -> dict[str, float]:
    return {
        "kcal": macros.calories_kcal,
        "protein_g": macros.protein_g,
        "carbs_g": macros.carbs_g,
        "fat_g": macros.fat_g,
        "fiber_g": macros.fiber_g,
        "cost": cost,
    }


def _card_url(recipe: Recipe | None) -> str | None:
    if recipe is None:
        return None
    return f"/cards/recipe/{recipe.category.value}/{recipe.id}.html"


def _entry_out(entry: LogEntry, library: Library) -> DiaryEntry:
    return DiaryEntry(
        id=entry.entry_id,
        recipe=entry.recipe_id,
        title=entry.title,
        card_url=_card_url(library.recipes.get(entry.recipe_id)),
        session=entry.session_id,
        kcal=entry.macros.calories_kcal,
        protein_g=entry.macros.protein_g,
        carbs_g=entry.macros.carbs_g,
        fat_g=entry.macros.fat_g,
        fiber_g=entry.macros.fiber_g,
        cost=entry.cost,
    )


def _session_out(
    session: PrepSession,
    eaten: dict[tuple[str, str], int],
    policy: prep.Policy,
    in_window: bool,
    library: Library,
) -> Session:
    return Session(
        id=session.session_id,
        date=session.date.isoformat(),
        mode=policy.mode(session.date).value,
        in_window=in_window,
        items=[
            SessionItem(
                recipe=item.recipe_id,
                title=item.title,
                card_url=_card_url(library.recipes.get(item.recipe_id)),
                batches=item.batches,
                ad_hoc=item.ad_hoc,
                servings=item.servings,
                portions=item.portions,
                eaten=eaten.get((session.session_id, item.recipe_id), 0),
                kcal=item.macros.calories_kcal,
                protein_g=item.macros.protein_g,
                cost=item.cost,
            )
            for item in session.items
        ],
    )


def week_response(
    week: str, diary: prep.Diary, today: datetime.date, library: Library
) -> DiaryWeek:
    """The full week for the UI: all 7 days, its session cards, totals."""
    policy = prep.Policy(today=today)
    dates = week_dates(week)
    dto = diary.weeks.get(week)
    logged = prepare_diary_week(dto) if dto is not None else None
    by_date = {d.date: d for d in logged.days} if logged is not None else {}
    days = []
    for date in dates:
        day = by_date.get(date)
        mode = policy.mode(date).value
        if day is None:
            days.append(
                DiaryDay(
                    date=date.isoformat(),
                    mode=mode,
                    meals=[],
                    totals=_totals(0.0, MacrosInfo.zero()),
                )
            )
            continue
        days.append(
            DiaryDay(
                date=date.isoformat(),
                mode=mode,
                meals=[
                    DiaryMeal(
                        mealtime=meal.mealtime.value,
                        entries=[_entry_out(e, library) for e in meal.entries],
                    )
                    for meal in day.meals()
                ],
                totals=_totals(day.cost, day.macros),
            )
        )
    totals = (
        _totals(logged.total_cost, logged.total_macros)
        if logged is not None
        else _totals(0.0, MacrosInfo.zero())
    )

    # Session cards: older sessions linked from this week, then every session
    # from the Sunday before through this Sunday, placeholders on empty
    # default days.
    start, end = prep.session_window(dates[0])
    eaten = {
        (str(sid), recipe): n
        for (sid, recipe), n in prep.link_counts(diary.weeks.values()).items()
    }
    linked_here = {
        entry.session
        for day_dto in (dto.days if dto is not None else ())
        for entry in day_dto.entries()
        if entry.session is not None
    }
    cards: list[tuple[datetime.date, Session]] = []
    taken: set[datetime.date] = set()
    for sid, session_dto in diary.sessions.items():
        in_window = start <= session_dto.date <= end
        if not in_window and sid not in linked_here:
            continue
        if in_window:
            taken.add(session_dto.date)
        cards.append(
            (
                session_dto.date,
                _session_out(
                    prepare_session(session_dto), eaten, policy, in_window, library
                ),
            )
        )
    for date in prep.default_session_dates(start, end):
        if date not in taken:
            cards.append(
                (
                    date,
                    Session(
                        id=None,
                        date=date.isoformat(),
                        mode=policy.mode(date).value,
                        in_window=True,
                        items=[],
                    ),
                )
            )
    cards.sort(key=lambda card: (card[1].in_window, card[0]))
    return DiaryWeek(
        week=week,
        today=today.isoformat(),
        exists=dto is not None,
        days=days,
        sessions=[card for _, card in cards],
        totals=totals,
    )
