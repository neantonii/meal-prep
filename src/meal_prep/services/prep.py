"""Prep-session rules: the edits that keep the diary and sessions aligned.

``docs/prep-sessions.md`` is the spec. A linked diary entry must align with
its session (the session lists its recipe, the entry is on or after the
session's date, links never exceed an item's portions). Which edits are
allowed, and whether they auto-fill sessions, depends on the editing mode:
Plan (after today), Log (today and earlier) or Admin (explicit switch).

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
# Auto-link looks this many days back, the entry's own day included.
AUTO_LINK_DAYS = 7

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


def usual_session(
    sessions: Iterable[PrepSessionDTO], date: datetime.date
) -> uuid.UUID | None:
    """The session a meal on ``date`` usually comes from: the latest one
    strictly before that day. Any other link (a same-day session, an older
    one) is unusual and worth showing."""
    earlier = [s for s in sessions if s.date < date]
    return max(earlier, key=lambda s: s.date).id if earlier else None


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
        """In Plan, batches follow the linked meals: the fewest whole batches
        that cover them, at least one (an item can be listed before its meals
        are planned). Once the session's day arrives they stay as they were:
        a record of what was made. Admin edits are left as they are."""
        if self.policy.admin:
            return
        counts = link_counts(self.weeks.values())
        for session in list(self.sessions.values()):
            if self.policy.mode(session.date) is not Mode.PLAN:
                continue
            items = [
                item
                if (b := _batches_for(counts[(session.id, item.recipe)], item.servings))
                == item.batches
                else item.model_copy(update={"batches": b})
                for item in session.items
            ]
            if items != list(session.items):
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
        """Plan auto-fill: let ``session_id`` take one more ``recipe_id``.

        Adds the item (1 batch) or raises its batches until one more portion
        fits, but only when the session itself is still in Plan; otherwise
        it leaves the session alone and ``check`` reports the problem.
        """
        session = self.session(session_id)
        if session.date > entry_date:
            return  # check() explains: the session is later than the entry
        if self.policy.mode(session.date) is not Mode.PLAN:
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

    def auto_link(self, recipe_id: str, date: datetime.date) -> uuid.UUID | None:
        """The session a palette drop on ``date`` links to (Plan auto-link).

        First the latest session in the last ``AUTO_LINK_DAYS`` that lists the
        recipe with a free portion; else the latest Plan day in that span
        that has a session or is a default prep day (auto-filled, creating
        the session when needed); else ``None``.
        """
        start = date - datetime.timedelta(days=AUTO_LINK_DAYS - 1)
        recent = sorted(
            (s for s in self.sessions.values() if start <= s.date <= date),
            key=lambda s: s.date,
            reverse=True,
        )
        counts = link_counts(self.weeks.values())
        for session in recent:
            item = _item(session, recipe_id)
            if item is not None and counts[(session.id, recipe_id)] < _portions(item):
                return session.id
        plan_days = sorted(
            {
                day
                for day in (
                    *(s.date for s in recent),
                    *default_session_dates(start, date),
                )
                if self.policy.mode(day) is Mode.PLAN
            },
            reverse=True,
        )
        if not plan_days:
            return None
        day = plan_days[0]
        existing = self.session_on(day)
        if existing is not None:
            self.make_room(existing.id, recipe_id, date)
            return existing.id
        created = PrepSessionDTO(
            id=uuid.uuid4(), date=day, items=[freeze_item(self.recipe(recipe_id))]
        )
        self.put_session(created)
        return created.id


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
    ``"auto"`` (a palette drop: auto-linked in Plan, unlinked otherwise)."""
    draft = _Draft(diary, policy, recipes)
    mode = policy.mode(date)
    session: uuid.UUID | None
    if link == "auto":
        session = draft.auto_link(recipe.id, date) if mode is Mode.PLAN else None
    elif link is None:
        session = None
    else:
        if mode is Mode.LOG:
            raise RuleError(
                f"{day_label(date)} is in Log mode: new entries can't be linked "
                "to a session"
            )
        draft.session(link)  # must exist
        if mode is Mode.PLAN:
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
    """Remove one entry (any mode). In Plan its session shrinks to fit the
    remaining meals; in Log the portion stays made (spare)."""
    draft = _Draft(diary, policy, {})
    draft.put_week(week, entries.remove_entry(_week_of(draft, week), entry_id))
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
    """Move or reorder one entry, keeping its link while it still holds.

    In Plan a link the move breaks (the entry now precedes its session) is
    re-linked by the auto-link rule; in Log and Admin the move is refused.
    """
    draft = _Draft(diary, policy, recipes)
    current = _week_of(draft, week)
    old_date, _, entry = entries.find_entry(current, entry_id)
    moved = entries.move_entry(current, entry_id, date, mealtime, position)
    draft.put_week(week, moved)
    session = entry.session
    if (
        session is not None
        and policy.mode(old_date, date) is Mode.PLAN
        and (session not in draft.sessions or draft.sessions[session].date > date)
    ):
        unlinked = entries.set_entry_session(moved, entry_id, None)
        draft.put_week(week, unlinked)
        session = draft.auto_link(entry.recipe, date)
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
) -> Change:
    """Link one entry to ``session`` (``None`` unlinks). Plan auto-fills;
    Log refuses; Admin links only when the rules hold."""
    draft = _Draft(diary, policy, recipes)
    current = _week_of(draft, week)
    date, _, entry = entries.find_entry(current, entry_id)
    if entry.session == session:
        return Change()
    mode = policy.mode(date)
    if mode is Mode.LOG:
        raise RuleError(
            f"{day_label(date)} is in Log mode: an entry's session can only "
            "change in Admin mode"
        )
    unlinked = entries.set_entry_session(current, entry_id, None)
    draft.put_week(week, unlinked)
    if session is not None:
        draft.session(session)  # must exist
        if mode is Mode.PLAN:
            draft.make_room(session, entry.recipe, date)
        draft.put_week(week, entries.set_entry_session(unlinked, entry_id, session))
    draft.check([session])
    return draft.change()


# ---------------------------------------------------------------------------
# Session edits
# ---------------------------------------------------------------------------


def add_item(
    diary: Diary,
    policy: Policy,
    date: datetime.date,
    recipe: Recipe,
    batches: int = 1,
) -> tuple[Change, uuid.UUID]:
    """Add ``recipe`` to the session on ``date``, creating the session when
    the day has none. Refused in Log: nothing can be made after the fact."""
    draft = _Draft(diary, policy, {})
    if policy.mode(date) is Mode.LOG:
        raise RuleError(
            f"The {day_label(date)} session already happened: adding to it is "
            "Admin only"
        )
    item = freeze_item(recipe, batches=batches)
    session = draft.session_on(date)
    if session is None:
        session = PrepSessionDTO(id=uuid.uuid4(), date=date, items=[item])
    elif _item(session, recipe.id) is not None:
        raise RuleError(f"The {day_label(date)} session already has {recipe.title}")
    else:
        session = session.model_copy(update={"items": [*session.items, item]})
    draft.put_session(session)
    return draft.change(), session.id


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


def update_item(
    diary: Diary,
    policy: Policy,
    session_id: uuid.UUID,
    recipe_id: str,
    batches: int,
) -> Change:
    """Admin only: set an item's batches, keeping its frozen numbers. In
    Plan batches follow the meals and in Log they record what was made, so
    this is for corrections; portions never drop below the linked entries."""
    if not policy.admin:
        raise RuleError("Batches follow the planned meals; changing them is Admin only")
    draft = _Draft(diary, policy, {})
    session, item = _session_item(draft, session_id, recipe_id)
    if batches == item.batches:
        return Change()
    changed = SessionItemDTO.model_validate({**item.model_dump(), "batches": batches})
    items = [changed if i is item else i for i in session.items]
    draft.put_session(session.model_copy(update={"items": items}))
    draft.check([session_id])
    return draft.change()


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
