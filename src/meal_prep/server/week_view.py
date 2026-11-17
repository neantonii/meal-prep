"""Build the week page the UI shows: 7 days, session cards, the two slots
without a date and totals.

Read-only: turns the loaded diary (``services.prep.Diary``) into the API
shapes, with titles and numbers from the frozen entries and session items.
"""

from __future__ import annotations

import datetime
import uuid
from collections import Counter
from collections.abc import Collection, Mapping
from dataclasses import dataclass

from meal_prep.dtos.log import RecipeEntryDTO
from meal_prep.enums import Mealtime, RecipeCategory
from meal_prep.models.ingredient import MacrosInfo
from meal_prep.models.library import Library
from meal_prep.models.log import LogEntry, TakeoutLogEntry
from meal_prep.models.recipe import Recipe
from meal_prep.models.session import NeedShare as ModelNeedShare
from meal_prep.models.session import PrepSession
from meal_prep.renderer import category_display_name
from meal_prep.server.api_models import (
    AisleNeeds,
    Bin,
    BinnedMeal,
    DiaryDay,
    DiaryEntry,
    DiaryMeal,
    DiaryWeek,
    MealRef,
    NeededIngredient,
    NeedShare,
    RecipeEntryOut,
    Session,
    SessionDetail,
    SessionItem,
    TakeoutEntryOut,
    UnassignedRecipe,
    UnassignedSource,
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


def _ingredient_card_url(ingredient_id: str, library: Library) -> str | None:
    ingredient = library.ingredients.get(ingredient_id)
    if ingredient is None:
        return None
    return f"/cards/ingredient/{ingredient.aisle.value}/{ingredient.id}.html"


def _needs_out(
    session: PrepSession,
    library: Library,
    have: Mapping[str, Collection[str]] | None = None,
    always: Collection[str] = (),
) -> list[AisleNeeds]:
    """``have`` maps recipe ids to the ingredient ids ticked for them."""
    ticked = have or {}

    def share_out(ing: str, share: ModelNeedShare) -> NeedShare:
        return NeedShare(
            recipe=share.recipe_id,
            title=share.title,
            packages=share.packages,
            grams=share.grams,
            cost=share.cost,
            have=ing in ticked.get(share.recipe_id, ()),
        )

    return [
        AisleNeeds(
            aisle=None if group.aisle is None else group.aisle.value,
            cost=group.cost,
            ingredients=[
                NeededIngredient(
                    ingredient=ing.ingredient_id,
                    name=ing.name,
                    card_url=_ingredient_card_url(ing.ingredient_id, library),
                    product=None if ing.package is None else ing.package.product,
                    package_amount=None if ing.package is None else ing.package.amount,
                    package_unit=None if ing.package is None else ing.package.unit,
                    packages=ing.packages,
                    grams=ing.grams,
                    cost=ing.cost,
                    recipes=list(ing.recipes),
                    shares=(
                        shares := [share_out(ing.ingredient_id, s) for s in ing.shares]
                    ),
                    have=all(s.have for s in shares),
                    always=ing.ingredient_id in always,
                )
                for ing in group.ingredients
            ],
        )
        for group in session.needs()
    ]


@dataclass(frozen=True, slots=True)
class _Batch:
    """What a meal needs to know about the recipe line it is a portion of."""

    session_date: datetime.date
    fridge_days: int | None
    freezer_friendly: bool | None


type _Batches = dict[tuple[str, str], _Batch]


def _batches(diary: prep.Diary) -> _Batches:
    return {
        (str(sid), item.recipe): _Batch(
            session.date, item.fridge_days, item.freezer_friendly
        )
        for sid, session in diary.sessions.items()
        for item in session.items
    }


def _entry_out(
    entry: LogEntry, library: Library, date: datetime.date, batches: _Batches
) -> DiaryEntry:
    m = entry.macros
    if isinstance(entry, TakeoutLogEntry):
        return TakeoutEntryOut(
            id=entry.entry_id,
            title=entry.title,
            kcal=m.calories_kcal,
            protein_g=m.protein_g,
            carbs_g=m.carbs_g,
            fat_g=m.fat_g,
            cost=entry.cost,
        )
    batch = batches.get((entry.session_id or "", entry.recipe_id))
    return RecipeEntryOut(
        id=entry.entry_id,
        title=entry.title,
        kcal=m.calories_kcal,
        protein_g=m.protein_g,
        carbs_g=m.carbs_g,
        fat_g=m.fat_g,
        recipe=entry.recipe_id,
        card_url=_card_url(library.recipes.get(entry.recipe_id)),
        session=entry.session_id,
        # Frozen is implied: eaten later than the dish keeps in the fridge.
        frozen=(
            batch is not None
            and batch.fridge_days is not None
            and (date - batch.session_date).days > batch.fridge_days
        ),
        freezer_friendly=None if batch is None else batch.freezer_friendly,
        fiber_g=m.fiber_g,
        cost=entry.cost,
        planned=entry.planned,
    )


@dataclass(frozen=True, slots=True)
class _Meals:
    """Where the portions of every recipe line are, by (session id, recipe
    id): on days, unassigned, binned."""

    days: dict[tuple[str, str], list[MealRef]]
    unassigned: Counter[tuple[str, str]]
    binned: Counter[tuple[str, str]]
    planned: Counter[str]  # meals the planner placed, per session id


def _planned_by_session(diary: prep.Diary) -> Counter[str]:
    """Planned (not yet accepted) meals per session id, on days and
    unassigned."""
    counts: Counter[str] = Counter(
        str(link.session)
        for link in prep.linked_entries(diary.weeks.values())
        if link.entry.planned
    )
    counts.update(str(m.session) for m in diary.unassigned if m.planned and m.session)
    return counts


def _meals_by_item(diary: prep.Diary) -> _Meals:
    def by_item(counts: Counter[tuple[uuid.UUID, str]]) -> Counter[tuple[str, str]]:
        return Counter({(str(sid), recipe): n for (sid, recipe), n in counts.items()})

    return _Meals(
        days={
            (str(sid), recipe): [
                MealRef(date=date.isoformat(), mealtime=mealtime.value)
                for date, mealtime in found
            ]
            for (sid, recipe), found in prep.linked_meals(diary.weeks.values()).items()
        },
        unassigned=by_item(prep.slot_counts(diary.unassigned)),
        binned=by_item(prep.slot_counts(diary.bin)),
        planned=_planned_by_session(diary),
    )


def _unassigned_out(diary: prep.Diary, library: Library) -> list[UnassignedRecipe]:
    """The unassigned slot by recipe, in title order; each with its
    sessions, latest first. Portions whose session is gone are left out
    (nothing can be done with them)."""
    found: dict[str, list[tuple[datetime.date, uuid.UUID]]] = {}
    first: dict[str, RecipeEntryDTO] = {}
    ids: dict[str, list[tuple[datetime.date, str]]] = {}
    for meal in diary.unassigned:
        session = diary.sessions.get(meal.session) if meal.session else None
        if session is None:
            continue
        found.setdefault(meal.recipe, []).append((session.date, session.id))
        ids.setdefault(meal.recipe, []).append((session.date, str(meal.id)))
        first.setdefault(meal.recipe, meal)
    batches = _batches(diary)
    rows = []
    for recipe_id, sources in found.items():
        meal = first[recipe_id]
        counts = Counter(sources)
        latest = max(counts)
        rows.append(
            UnassignedRecipe(
                recipe=recipe_id,
                title=meal.title,
                card_url=_card_url(library.recipes.get(recipe_id)),
                count=len(sources),
                kcal=meal.calories_kcal,
                protein_g=meal.protein_g,
                freezer_friendly=batches[(str(latest[1]), recipe_id)].freezer_friendly
                if (str(latest[1]), recipe_id) in batches
                else None,
                sources=[
                    UnassignedSource(
                        session=str(sid), date=date.isoformat(), count=count
                    )
                    for (date, sid), count in sorted(counts.items(), reverse=True)
                ],
                meals=[meal_id for _, meal_id in sorted(ids[recipe_id])],
            )
        )
    return sorted(rows, key=lambda row: row.title.casefold())


def _bin_out(diary: prep.Diary) -> Bin:
    meals = sorted(diary.bin, key=lambda m: m.binned, reverse=True)
    return Bin(
        count=len(meals),
        cost=sum(m.cost for m in meals),
        meals=[
            BinnedMeal(
                id=str(m.id),
                recipe=m.recipe,
                title=m.title,
                cost=m.cost,
                binned=m.binned.isoformat(),
                session=str(m.session),
                session_date=(
                    session.date.isoformat()
                    if m.session and (session := diary.sessions.get(m.session))
                    else None
                ),
            )
            for m in meals
        ],
    )


_CATEGORY_ORDER = {category: i for i, category in enumerate(RecipeCategory)}


def _category_rank(recipe: Recipe | None) -> int:
    """Session items list by category, in ``RecipeCategory`` order (the
    palette's); items whose recipe is gone come last."""
    return _CATEGORY_ORDER[recipe.category] if recipe else len(_CATEGORY_ORDER)


def _session_out(
    session: PrepSession,
    meals: _Meals,
    policy: prep.Policy,
    in_window: bool,
    library: Library,
) -> Session:
    return Session(
        id=session.session_id,
        date=session.date.isoformat(),
        mode=policy.mode(session.date).value,
        in_window=in_window,
        planned=meals.planned[session.session_id],
        items=[
            SessionItem(
                recipe=item.recipe_id,
                title=item.title,
                card_url=_card_url(library.recipes.get(item.recipe_id)),
                category=(
                    recipe.category.value
                    if (recipe := library.recipes.get(item.recipe_id))
                    else None
                ),
                category_label=(
                    category_display_name(recipe.category) if recipe else None
                ),
                batches=item.batches,
                servings=item.servings,
                portions=item.portions,
                eaten=len(meals.days.get((session.session_id, item.recipe_id), [])),
                meals=meals.days.get((session.session_id, item.recipe_id), []),
                unassigned=meals.unassigned[(session.session_id, item.recipe_id)],
                binned=meals.binned[(session.session_id, item.recipe_id)],
                kcal=item.macros.calories_kcal,
                protein_g=item.macros.protein_g,
                cost=item.cost,
            )
            for item in sorted(
                session.items,
                key=lambda i: _category_rank(library.recipes.get(i.recipe_id)),
            )
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
    batches = _batches(diary)
    days = []
    for date in dates:
        day = by_date.get(date)
        mode = policy.mode(date).value
        settled = [m.value for m in Mealtime if policy.locked(date, m)]
        if day is None:
            days.append(
                DiaryDay(
                    date=date.isoformat(),
                    mode=mode,
                    settled=settled,
                    meals=[],
                    totals=_totals(0.0, MacrosInfo.zero()),
                )
            )
            continue
        days.append(
            DiaryDay(
                date=date.isoformat(),
                mode=mode,
                settled=settled,
                meals=[
                    DiaryMeal(
                        mealtime=meal.mealtime.value,
                        entries=[
                            _entry_out(e, library, date, batches) for e in meal.entries
                        ],
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
    meals = _meals_by_item(diary)
    linked_here = {
        link.session for link in prep.linked_entries([dto] if dto is not None else [])
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
                    prepare_session(session_dto), meals, policy, in_window, library
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
        unassigned=_unassigned_out(diary, library),
        bin=_bin_out(diary),
        totals=totals,
    )


def session_detail(
    session_id: uuid.UUID,
    diary: prep.Diary,
    today: datetime.date,
    library: Library,
    always: Collection[str] = (),
) -> SessionDetail:
    """One session for its own page; ``SessionNotFoundError`` if unknown.
    ``always`` holds the staples (ingredient ids on hand in every session)."""
    dto = diary.sessions.get(session_id)
    if dto is None:
        raise prep.SessionNotFoundError(f"No session {session_id}")
    session = prepare_session(dto)
    card = _session_out(
        session, _meals_by_item(diary), prep.Policy(today=today), True, library
    )
    year, number, _ = dto.date.isocalendar()
    return SessionDetail(
        session=card,
        today=today.isoformat(),
        week=f"{year}-W{number:02d}",
        totals={
            "portions": sum(item.portions for item in session.items),
            "cost": sum(item.portions * item.cost for item in session.items),
            "kcal": sum(
                item.portions * item.macros.calories_kcal for item in session.items
            ),
            "protein_g": sum(
                item.portions * item.macros.protein_g for item in session.items
            ),
        },
        needs=_needs_out(session, library, dto.have, set(always)),
    )
