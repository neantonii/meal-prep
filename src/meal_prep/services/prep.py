"""Prep-session rules: the edits that keep the diary and sessions aligned.

``docs/prep-sessions.md`` is the spec. A linked diary entry must align with
its session (the session lists its recipe, the entry is on or after the
session's date, links never exceed an item's portions). Meals belong to prep
cycles (the preset session days); a cycle's meals lock the day after the
next session day. A session grows only while open (today or later); a
closed one gives free portions only. Admin edits locked meals and grows
closed sessions.

Every edit works on a whole-diary snapshot (all weeks and all sessions,
since links span weeks) and returns a ``Change``: the week and session
documents to write or delete. Storage is the caller's job. A refused edit
raises ``RuleError`` with a message meant for the user.
"""

from __future__ import annotations

import datetime
import math
import uuid
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

from meal_prep.dtos.log import DiaryEntryDTO, DiaryWeekDTO
from meal_prep.dtos.session import PrepSessionDTO, SessionItemDTO
from meal_prep.enums import Mealtime
from meal_prep.models.recipe import Recipe
from meal_prep.services import diary as entries
from meal_prep.services.sessions import freeze_item, whole_servings

# Default prep days, as ``date.weekday()``: Sunday, Tuesday, Thursday.
DEFAULT_SESSION_WEEKDAYS = frozenset({6, 1, 3})
# Meals eaten in the evening, after that day's prep: a session day's own
# dinner and snacks belong to its cycle; breakfast and lunch to the one before.
EVENING = frozenset({Mealtime.DINNER, Mealtime.SNACKS})

type Link = uuid.UUID | Literal["auto"] | None


class Mode(StrEnum):
    PLAN = "plan"
    LOG = "log"
    ADMIN = "admin"


class RuleError(ValueError):
    """An edit the prep-session rules refuse; the message is user-facing."""


class SessionNotFoundError(LookupError):
    """No session (or no such item in it) with the given id."""


@dataclass(frozen=True, slots=True)
class Policy:
    """Who edits when: ``today`` splits Plan from Log; ``admin`` overrides."""

    today: datetime.date
    admin: bool = False

    def mode(self, *days: datetime.date) -> Mode:
        """The mode for an edit touching ``days``: Log if any is not ahead."""
        if self.admin:
            return Mode.ADMIN
        return Mode.LOG if any(day <= self.today for day in days) else Mode.PLAN

    def session_open(self, day: datetime.date) -> bool:
        """A session on ``day`` can still take new meals and grow: from today
        on (the prep happens during the session's day), or any day in Admin."""
        return self.admin or day >= self.today

    def locked(self, date: datetime.date, mealtime: Mealtime) -> bool:
        """A meal is settled once its prep cycle locks: the day after the
        next session day. Today's meals never lock; Admin edits any."""
        if self.admin or date >= self.today:
            return False
        return self.today > next_session_day(cycle_day(date, mealtime))


@dataclass(frozen=True, slots=True)
class Diary:
    """Every diary week (by week id) and every session (by id)."""

    weeks: Mapping[str, DiaryWeekDTO]
    sessions: Mapping[uuid.UUID, PrepSessionDTO]


@dataclass(frozen=True, slots=True)
class Change:
    """Documents to write; ``None`` deletes that week or session."""

    weeks: Mapping[str, DiaryWeekDTO | None] = field(default_factory=dict)
    sessions: Mapping[uuid.UUID, PrepSessionDTO | None] = field(default_factory=dict)


def day_label(date: datetime.date) -> str:
    """Short human date for messages, e.g. ``Sun 1 Nov``."""
    return f"{date:%a} {date.day} {date:%b}"


def session_window(monday: datetime.date) -> tuple[datetime.date, datetime.date]:
    """Session dates a week page shows: the Sunday before through its Sunday."""
    return monday - datetime.timedelta(days=1), monday + datetime.timedelta(days=6)


def default_session_dates(
    start: datetime.date, end: datetime.date
) -> tuple[datetime.date, ...]:
    """Default prep days (Sun, Tue, Thu) from ``start`` to ``end`` inclusive."""
    days = (end - start).days + 1
    return tuple(
        day
        for offset in range(max(days, 0))
        if (day := start + datetime.timedelta(days=offset)).weekday()
        in DEFAULT_SESSION_WEEKDAYS
    )


def cycle_day(date: datetime.date, mealtime: Mealtime) -> datetime.date:
    """The session day a meal belongs to: the latest preset day (Sun, Tue,
    Thu) on or before ``date``; ``date`` itself only for dinner and snacks."""
    day = date if mealtime in EVENING else date - datetime.timedelta(days=1)
    while day.weekday() not in DEFAULT_SESSION_WEEKDAYS:
        day -= datetime.timedelta(days=1)
    return day


def next_session_day(day: datetime.date) -> datetime.date:
    """The first preset session day after ``day``."""
    day += datetime.timedelta(days=1)
    while day.weekday() not in DEFAULT_SESSION_WEEKDAYS:
        day += datetime.timedelta(days=1)
    return day


def linked_meals(
    weeks: Iterable[DiaryWeekDTO],
) -> dict[tuple[uuid.UUID, str], list[tuple[datetime.date, Mealtime]]]:
    """The meals linked per (session id, recipe id), over all ``weeks``, in
    date and mealtime order."""
    meals: dict[tuple[uuid.UUID, str], list[tuple[datetime.date, Mealtime]]] = {}
    order = list(Mealtime)
    for week in weeks:
        for day in week.days:
            for mealtime in Mealtime:
                for entry in getattr(day, mealtime.value) or ():
                    if entry.session is not None:
                        key = (entry.session, entry.recipe)
                        meals.setdefault(key, []).append((day.date, mealtime))
    for found in meals.values():
        found.sort(key=lambda m: (m[0], order.index(m[1])))
    return meals


def link_counts(weeks: Iterable[DiaryWeekDTO]) -> Counter[tuple[uuid.UUID, str]]:
    """Linked entries per (session id, recipe id), over all ``weeks``."""
    counts: Counter[tuple[uuid.UUID, str]] = Counter()
    for week in weeks:
        for day in week.days:
            for entry in day.entries():
                if entry.session is not None:
                    counts[(entry.session, entry.recipe)] += 1
    return counts


def _portions(item: SessionItemDTO) -> int:
    return item.batches * item.servings


def _batches_for(portions: int, servings: int) -> int:
    """Fewest whole batches that make ``portions`` (at least one)."""
    return max(1, math.ceil(portions / servings))


class _Draft:
    """A working copy of the diary that records what an edit changed."""

    def __init__(self, diary: Diary, policy: Policy, recipes: Mapping[str, Recipe]):
        self.policy = policy
        self.recipes = recipes
        self.weeks: dict[str, DiaryWeekDTO] = dict(diary.weeks)
        self.sessions: dict[uuid.UUID, PrepSessionDTO] = dict(diary.sessions)
        self._weeks_out: dict[str, DiaryWeekDTO | None] = {}
        self._sessions_out: dict[uuid.UUID, PrepSessionDTO | None] = {}

    # -- documents ----------------------------------------------------------

    def week(self, week: str) -> DiaryWeekDTO | None:
        return self.weeks.get(week)

    def put_week(self, week: str, dto: DiaryWeekDTO | None) -> None:
        if dto is None:
            self.weeks.pop(week, None)
        else:
            self.weeks[week] = dto
        self._weeks_out[week] = dto

    def session(self, session_id: uuid.UUID) -> PrepSessionDTO:
        try:
            return self.sessions[session_id]
        except KeyError:
            raise SessionNotFoundError(f"No session {session_id}") from None

    def session_on(self, date: datetime.date) -> PrepSessionDTO | None:
        return next((s for s in self.sessions.values() if s.date == date), None)

    def put_session(self, session: PrepSessionDTO) -> None:
        # Re-validate (unique recipes, at least one item).
        session = PrepSessionDTO.model_validate(session.model_dump())
        self.sessions[session.id] = session
        self._sessions_out[session.id] = session

    def drop_session(self, session_id: uuid.UUID) -> None:
        self.sessions.pop(session_id, None)
        self._sessions_out[session_id] = None

    def change(self) -> Change:
        self.derive_batches()
        return Change(weeks=dict(self._weeks_out), sessions=dict(self._sessions_out))

    def derive_batches(self) -> None:
        """In Plan, a session follows its linked meals: each item's batches
        are the fewest whole batches that cover its meals; an item with no
        meals left is removed, and a session with no items left is deleted.
        Once the session's day arrives it stays as it was: a record of what
        was made. Admin edits are left as they are."""
        if self.policy.admin:
            return
        counts = link_counts(self.weeks.values())
        for session in list(self.sessions.values()):
            if self.policy.mode(session.date) is not Mode.PLAN:
                continue
            items = []
            for item in session.items:
                meals = counts[(session.id, item.recipe)]
                if meals == 0:
                    continue
                batches = _batches_for(meals, item.servings)
                items.append(
                    item
                    if batches == item.batches
                    else item.model_copy(update={"batches": batches})
                )
            if not items:
                self.drop_session(session.id)
            elif items != list(session.items):
                self.put_session(session.model_copy(update={"items": items}))

    # -- links ----------------------------------------------------------------

    def linked(self) -> list[tuple[datetime.date, DiaryEntryDTO]]:
        return [
            (day.date, entry)
            for week in self.weeks.values()
            for day in week.days
            for entry in day.entries()
            if entry.session is not None
        ]

    def count(self, session_id: uuid.UUID, recipe_id: str) -> int:
        return link_counts(self.weeks.values())[(session_id, recipe_id)]

    def check(self, session_ids: Iterable[uuid.UUID | None]) -> None:
        """Refuse unless every entry linked to ``session_ids`` aligns."""
        wanted = {sid for sid in session_ids if sid is not None}
        if not wanted:
            return
        counts: Counter[tuple[uuid.UUID, str]] = Counter()
        for date, entry in self.linked():
            if entry.session not in wanted:
                continue
            assert entry.session is not None
            session = self.sessions.get(entry.session)
            if session is None:
                raise RuleError(f"{entry.title}: its prep session no longer exists")
            label = day_label(session.date)
            if _item(session, entry.recipe) is None:
                raise RuleError(f"The {label} session has no {entry.title}")
            if date < session.date:
                raise RuleError(
                    f"{entry.title} on {day_label(date)} can't come from the "
                    f"later {label} session"
                )
            counts[(entry.session, entry.recipe)] += 1
        for sid in wanted:
            session = self.sessions.get(sid)
            if session is None:
                continue
            for item in session.items:
                made = _portions(item)
                eaten = counts[(sid, item.recipe)]
                if eaten > made:
                    raise RuleError(
                        f"The {day_label(session.date)} session's {item.title} "
                        f"is full: {made} portion{'' if made == 1 else 's'}, "
                        f"{eaten} linked entries"
                    )

    def recipe(self, recipe_id: str) -> Recipe:
        try:
            return self.recipes[recipe_id]
        except KeyError:
            raise RuleError(f"Recipe '{recipe_id}' no longer exists") from None

    def make_room(
        self, session_id: uuid.UUID, recipe_id: str, entry_date: datetime.date
    ) -> None:
        """Let ``session_id`` take one more ``recipe_id`` (an explicit link).

        Adds the item (1 batch) or raises its batches until one more portion
        fits: for a session still in Plan, or any session in Admin (the link
        is the deliberate correction). Today's session is still open: the
        prep happens during its day. A session that already happened is
        otherwise left alone and ``check`` reports the problem.
        """
        session = self.session(session_id)
        if session.date > entry_date:
            return  # check() explains: the session is later than the entry
        if not self.policy.session_open(session.date):
            return
        item = _item(session, recipe_id)
        needed = self.count(session_id, recipe_id) + 1
        if item is None:
            recipe = self.recipe(recipe_id)
            batches = _batches_for(needed, whole_servings(recipe))
            new_items = [*session.items, freeze_item(recipe, batches=batches)]
        else:
            if _portions(item) >= needed:
                return
            batches = _batches_for(needed, item.servings)
            new_items = [
                i.model_copy(update={"batches": batches}) if i is item else i
                for i in session.items
            ]
        self.put_session(session.model_copy(update={"items": new_items}))

    def auto_link(
        self, recipe_id: str, date: datetime.date, mealtime: Mealtime
    ) -> uuid.UUID | None:
        """The session a recipe drop on ``date`` links to: the session on the
        meal's cycle day (``cycle_day``). A free portion there, if any; else,
        while that day is open (today or later), the session grows to fit,
        created when needed; else ``None``. The same in Admin, and an earlier
        cycle is never reached into (a manual link may pick one)."""
        day = cycle_day(date, mealtime)
        session = self.session_on(day)
        if session is not None:
            item = _item(session, recipe_id)
            if item is not None and self.count(session.id, recipe_id) < _portions(item):
                return session.id
        if day < self.policy.today:
            return None
        if session is not None:
            self.make_room(session.id, recipe_id, date)
            return session.id
        created = PrepSessionDTO(
            id=uuid.uuid4(), date=day, items=[freeze_item(self.recipe(recipe_id))]
        )
        self.put_session(created)
        return created.id


def _check_open(policy: Policy, date: datetime.date, mealtime: Mealtime) -> None:
    """Refuse an edit to a settled meal (its prep cycle locked)."""
    if policy.locked(date, mealtime):
        raise RuleError(
            f"{day_label(date)} {mealtime.value} is settled: its prep cycle "
            "ended (Admin can still change it)"
        )


def _item(session: PrepSessionDTO, recipe_id: str) -> SessionItemDTO | None:
    return next((i for i in session.items if i.recipe == recipe_id), None)


def _week_of(draft: _Draft, week: str) -> DiaryWeekDTO:
    dto = draft.week(week)
    if dto is None:
        raise entries.EntryNotFoundError(f"No entries in week {week}")
    return dto


# ---------------------------------------------------------------------------
# Entry edits
# ---------------------------------------------------------------------------


def add_entry(
    diary: Diary,
    policy: Policy,
    recipes: Mapping[str, Recipe],
    week: str,
    date: datetime.date,
    mealtime: Mealtime,
    recipe: Recipe,
    position: int | None = None,
    link: Link = "auto",
) -> tuple[Change, DiaryEntryDTO]:
    """Add an entry for ``recipe``; ``link`` is a session id, ``None`` or
    ``"auto"`` (a recipe drop: auto-linked, on any day, Admin or not)."""
    _check_open(policy, date, mealtime)
    draft = _Draft(diary, policy, recipes)
    session: uuid.UUID | None
    if link == "auto":
        session = draft.auto_link(recipe.id, date, mealtime)
    elif link is None:
        session = None
    else:
        draft.session(link)  # must exist
        draft.make_room(link, recipe.id, date)
        session = link
    dto, entry = entries.add_entry(
        draft.week(week), week, date, mealtime, recipe, position, session
    )
    draft.put_week(week, dto)
    draft.check([session])
    return draft.change(), entry


def remove_entry(
    diary: Diary, policy: Policy, week: str, entry_id: uuid.UUID
) -> Change:
    """Remove one entry unless it is settled. An open session shrinks to fit
    the remaining meals; a closed one keeps the portion made (spare)."""
    draft = _Draft(diary, policy, {})
    current = _week_of(draft, week)
    date, mealtime, _ = entries.find_entry(current, entry_id)
    _check_open(policy, date, mealtime)
    draft.put_week(week, entries.remove_entry(current, entry_id))
    return draft.change()


def move_entry(
    diary: Diary,
    policy: Policy,
    recipes: Mapping[str, Recipe],
    week: str,
    entry_id: uuid.UUID,
    date: datetime.date,
    mealtime: Mealtime,
    position: int | None = None,
) -> Change:
    """Move or reorder one entry (neither place settled), keeping its link
    while it still holds; a link the move breaks (the entry now precedes its
    session) is re-linked by the auto-link rule."""
    draft = _Draft(diary, policy, recipes)
    current = _week_of(draft, week)
    old_date, old_mealtime, entry = entries.find_entry(current, entry_id)
    _check_open(policy, old_date, old_mealtime)
    _check_open(policy, date, mealtime)
    moved = entries.move_entry(current, entry_id, date, mealtime, position)
    draft.put_week(week, moved)
    session = entry.session
    if session is not None and (
        session not in draft.sessions or draft.sessions[session].date > date
    ):
        unlinked = entries.set_entry_session(moved, entry_id, None)
        draft.put_week(week, unlinked)
        session = draft.auto_link(entry.recipe, date, mealtime)
        draft.put_week(week, entries.set_entry_session(unlinked, entry_id, session))
    draft.check([session])
    return draft.change()


def set_entry_session(
    diary: Diary,
    policy: Policy,
    recipes: Mapping[str, Recipe],
    week: str,
    entry_id: uuid.UUID,
    session: uuid.UUID | None,
    session_date: datetime.date | None = None,
) -> Change:
    """Link one entry (not settled) to ``session`` (``None`` unlinks), or to
    the session on ``session_date``, creating it with the entry's recipe when
    that day has none yet (only while open). An open session grows to fit; a
    closed one only gives a free portion (Admin grows any)."""
    draft = _Draft(diary, policy, recipes)
    current = _week_of(draft, week)
    date, mealtime, entry = entries.find_entry(current, entry_id)
    _check_open(policy, date, mealtime)
    if session_date is not None:
        existing = draft.session_on(session_date)
        if existing is not None:
            session = existing.id
        elif not policy.session_open(session_date):
            raise RuleError(
                f"The {day_label(session_date)} session already happened: "
                "adding to it is Admin only"
            )
        else:
            created = PrepSessionDTO(
                id=uuid.uuid4(),
                date=session_date,
                items=[freeze_item(draft.recipe(entry.recipe))],
            )
            draft.put_session(created)
            session = created.id
    if entry.session == session:
        return Change()
    unlinked = entries.set_entry_session(current, entry_id, None)
    draft.put_week(week, unlinked)
    if session is not None:
        draft.session(session)  # must exist
        draft.make_room(session, entry.recipe, date)
        draft.put_week(week, entries.set_entry_session(unlinked, entry_id, session))
    draft.check([session])
    return draft.change()


# ---------------------------------------------------------------------------
# Session edits
# ---------------------------------------------------------------------------


def _session_item(
    draft: _Draft, session_id: uuid.UUID, recipe_id: str
) -> tuple[PrepSessionDTO, SessionItemDTO]:
    session = draft.session(session_id)
    item = _item(session, recipe_id)
    if item is None:
        raise SessionNotFoundError(
            f"The {day_label(session.date)} session has no '{recipe_id}'"
        )
    return session, item


def remove_item(
    diary: Diary, policy: Policy, session_id: uuid.UUID, recipe_id: str
) -> Change:
    """Remove an item without linked entries; the last one deletes the
    session."""
    draft = _Draft(diary, policy, {})
    session, item = _session_item(draft, session_id, recipe_id)
    linked = draft.count(session_id, recipe_id)
    if linked:
        raise RuleError(
            f"{item.title} has {linked} linked entr{'y' if linked == 1 else 'ies'}: "
            "remove or unlink them first"
        )
    items = [i for i in session.items if i is not item]
    if items:
        draft.put_session(session.model_copy(update={"items": items}))
    else:
        draft.drop_session(session_id)
    return draft.change()


def set_have(
    diary: Diary,
    policy: Policy,
    session_id: uuid.UUID,
    shares: Iterable[tuple[str, str]],
    have: bool,
) -> Change:
    """Tick (``have``) or untick recipe shares of ingredients, as
    ``(recipe_id, ingredient_id)`` pairs, on a session's shopping checklist.
    Allowed in every mode: it records what is at home, not what was made or
    eaten."""
    draft = _Draft(diary, policy, {})
    session = draft.session(session_id)
    ticked = {(r, i) for r, ings in session.have.items() for i in ings}
    if have:
        ticked.update(shares)
    else:
        ticked.difference_update(shares)
    out: dict[str, list[str]] = {}
    for recipe, ingredient in ticked:
        out.setdefault(recipe, []).append(ingredient)
    draft.put_session(session.model_copy(update={"have": out}))
    return draft.change()


def move_session(
    diary: Diary, policy: Policy, session_id: uuid.UUID, date: datetime.date
) -> Change:
    """Move a session to another free day (Plan: both days ahead; Admin);
    every linked entry must stay on or after the new date."""
    draft = _Draft(diary, policy, {})
    session = draft.session(session_id)
    if session.date == date:
        return Change()
    if policy.mode(session.date, date) is Mode.LOG:
        raise RuleError(
            "Only sessions that haven't happened can move to a day ahead "
            "(Admin can move any)"
        )
    if draft.session_on(date) is not None:
        raise RuleError(f"{day_label(date)} already has a session")
    draft.put_session(session.model_copy(update={"date": date}))
    draft.check([session_id])
    return draft.change()


def delete_session(diary: Diary, policy: Policy, session_id: uuid.UUID) -> Change:
    """Delete a session that no entry links to (any mode)."""
    draft = _Draft(diary, policy, {})
    session = draft.session(session_id)
    linked = sum(draft.count(session_id, item.recipe) for item in session.items)
    if linked:
        raise RuleError(
            f"The {day_label(session.date)} session has {linked} linked "
            f"entr{'y' if linked == 1 else 'ies'}: remove or unlink them first"
        )
    draft.drop_session(session_id)
    return draft.change()
