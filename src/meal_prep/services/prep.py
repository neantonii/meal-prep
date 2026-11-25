"""Prep-session rules: the edits that keep the diary and sessions aligned.

``docs/prep-sessions.md`` and ``docs/freezer.md`` are the spec. Every
portion of a session batch is a meal with a home: a day (a week file), the
unassigned slot or the bin. A recipe meal gets its session when it is
created and keeps it; only a whole recipe line moves to another session.
Batches are stored: they change when a batch is added (a recipe dropped on
a day), removed, or two lines merge. The one hard rule is that the meals
linked to an item never exceed its portions, and a meal on a day is never
before its session.

Meals belong to prep cycles (the preset session days); a cycle's meals lock
the day after the next session day. A session dated before today is cooked:
its batches are a fact. Admin ignores both (settled and cooked) and nothing
else.

Every edit works on a whole-diary snapshot (all weeks, all sessions and the
two slots, since links span weeks) and returns a ``Change``: the documents
to write or delete. Storage is the caller's job. A refused edit raises
``RuleError`` with a message meant for the user.
"""

from __future__ import annotations

import datetime
import uuid
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

from meal_prep.dtos.log import (
    DiaryEntryDTO,
    DiaryWeekDTO,
    RecipeEntryDTO,
    TakeoutEntryDTO,
)
from meal_prep.dtos.session import PrepSessionDTO, SessionItemDTO
from meal_prep.dtos.slots import BinnedEntryDTO
from meal_prep.enums import Mealtime
from meal_prep.models.recipe import Recipe
from meal_prep.services import diary as entries
from meal_prep.services.sessions import freeze_item, portion_entry

# Default prep days, as ``date.weekday()``: Sunday, Tuesday, Thursday.
DEFAULT_SESSION_WEEKDAYS = frozenset({6, 1, 3})
# Meals eaten in the evening, after that day's prep: a session day's own
# dinner and snacks belong to its cycle; breakfast and lunch to the one before.
EVENING = frozenset({Mealtime.DINNER, Mealtime.SNACKS})

# The two homes without a date (``docs/freezer.md``).
type Slot = Literal["unassigned", "bin"]


@dataclass(frozen=True, slots=True)
class Day:
    """A place on a day; ``position`` is the index in the slot (``None``
    appends)."""

    date: datetime.date
    mealtime: Mealtime
    position: int | None = None


# Where a meal can be put.
type Place = Day | Slot


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
        """A session on ``day`` is still planned, so its batches can change:
        from today on (the prep happens during the session's day), or any
        day in Admin. Otherwise it is cooked: a fact."""
        return self.admin or day >= self.today

    def locked(self, date: datetime.date, mealtime: Mealtime) -> bool:
        """A meal is settled once its prep cycle locks: the day after the
        next session day. Today's meals never lock; Admin edits any."""
        if self.admin or date >= self.today:
            return False
        return self.today > next_session_day(cycle_day(date, mealtime))


@dataclass(frozen=True, slots=True)
class Diary:
    """Every diary week (by week id), every session (by id) and the two
    slots without a date."""

    weeks: Mapping[str, DiaryWeekDTO]
    sessions: Mapping[uuid.UUID, PrepSessionDTO]
    unassigned: Sequence[RecipeEntryDTO] = ()
    bin: Sequence[BinnedEntryDTO] = ()


@dataclass(frozen=True, slots=True)
class Change:
    """Documents to write; ``None`` deletes that week or session, and
    leaves a slot as it is."""

    weeks: Mapping[str, DiaryWeekDTO | None] = field(default_factory=dict)
    sessions: Mapping[uuid.UUID, PrepSessionDTO | None] = field(default_factory=dict)
    unassigned: Sequence[RecipeEntryDTO] | None = None
    bin: Sequence[BinnedEntryDTO] | None = None


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


def week_id(date: datetime.date) -> str:
    """The ISO week ``date`` falls in, as a week file names it."""
    year, number, _ = date.isocalendar()
    return f"{year}-W{number:02d}"


@dataclass(frozen=True, slots=True)
class Linked:
    """A recipe entry linked to a prep session, and where it was eaten."""

    date: datetime.date
    mealtime: Mealtime
    entry: RecipeEntryDTO
    session: uuid.UUID


def linked_entries(weeks: Iterable[DiaryWeekDTO]) -> Iterator[Linked]:
    """Every entry on a day linked to a prep session, over all ``weeks``, in
    date and mealtime order within each week. Only recipe entries link
    (takeout never does): session code loops over this and never sees
    takeout."""
    for week in weeks:
        for day in week.days:
            for mealtime in Mealtime:
                for entry in getattr(day, mealtime.value) or ():
                    if isinstance(entry, RecipeEntryDTO) and entry.session:
                        yield Linked(day.date, mealtime, entry, entry.session)


def linked_meals(
    weeks: Iterable[DiaryWeekDTO],
) -> dict[tuple[uuid.UUID, str], list[tuple[datetime.date, Mealtime]]]:
    """The meals on days per (session id, recipe id), over all ``weeks``, in
    date and mealtime order."""
    meals: dict[tuple[uuid.UUID, str], list[tuple[datetime.date, Mealtime]]] = {}
    for link in linked_entries(weeks):
        key = (link.session, link.entry.recipe)
        meals.setdefault(key, []).append((link.date, link.mealtime))
    order = list(Mealtime)
    for found in meals.values():
        found.sort(key=lambda m: (m[0], order.index(m[1])))
    return meals


def slot_counts(
    meals: Iterable[RecipeEntryDTO],
) -> Counter[tuple[uuid.UUID, str]]:
    """Meals of a slot per (session id, recipe id)."""
    return Counter((m.session, m.recipe) for m in meals if m.session is not None)


def claim_counts(diary: Diary) -> Counter[tuple[uuid.UUID, str]]:
    """Meals per (session id, recipe id), wherever they are: on days, in
    the unassigned slot and in the bin."""
    counts = Counter(
        (link.session, link.entry.recipe)
        for link in linked_entries(diary.weeks.values())
    )
    counts.update(slot_counts(diary.unassigned))
    counts.update(slot_counts(diary.bin))
    return counts


def _portions(item: SessionItemDTO) -> int:
    return item.batches * item.servings


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}{'' if count == 1 else 's'}"


class _Draft:
    """A working copy of the diary that records what an edit changed."""

    def __init__(self, diary: Diary, policy: Policy):
        self.policy = policy
        self.weeks: dict[str, DiaryWeekDTO] = dict(diary.weeks)
        self.sessions: dict[uuid.UUID, PrepSessionDTO] = dict(diary.sessions)
        self.unassigned: list[RecipeEntryDTO] = list(diary.unassigned)
        self.bin: list[BinnedEntryDTO] = list(diary.bin)
        self._weeks_out: dict[str, DiaryWeekDTO | None] = {}
        self._sessions_out: dict[uuid.UUID, PrepSessionDTO | None] = {}
        self._unassigned_out = False
        self._bin_out = False

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

    def put_unassigned(self, meals: Iterable[RecipeEntryDTO]) -> None:
        self.unassigned = list(meals)
        self._unassigned_out = True

    def put_bin(self, meals: Iterable[BinnedEntryDTO]) -> None:
        self.bin = list(meals)
        self._bin_out = True

    def change(self) -> Change:
        return Change(
            weeks=dict(self._weeks_out),
            sessions=dict(self._sessions_out),
            unassigned=tuple(self.unassigned) if self._unassigned_out else None,
            bin=tuple(self.bin) if self._bin_out else None,
        )

    # -- links ----------------------------------------------------------------

    def snapshot(self) -> Diary:
        return Diary(self.weeks, self.sessions, self.unassigned, self.bin)

    def count(self, session_id: uuid.UUID, recipe_id: str) -> int:
        """Every meal of one recipe line, wherever it is."""
        return claim_counts(self.snapshot())[(session_id, recipe_id)]

    def check(self, session_ids: Iterable[uuid.UUID | None]) -> None:
        """Refuse unless the meals linked to ``session_ids`` align: the
        session lists their recipe, a meal on a day is not before it, and
        an item never has more meals than portions."""
        wanted = {sid for sid in session_ids if sid is not None}
        if not wanted:
            return
        for link in linked_entries(self.weeks.values()):
            if link.session not in wanted:
                continue
            date, entry = link.date, link.entry
            session = self.sessions.get(link.session)
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
        counts = claim_counts(self.snapshot())
        for sid in wanted:
            session = self.sessions.get(sid)
            if session is None:
                continue
            for item in session.items:
                made = _portions(item)
                meals = counts[(sid, item.recipe)]
                if meals > made:
                    raise RuleError(
                        f"The {day_label(session.date)} session's {item.title} "
                        f"is full: {_plural(made, 'portion')}, "
                        f"{_plural(meals, 'meal')}"
                    )


def _check_open(policy: Policy, date: datetime.date, mealtime: Mealtime) -> None:
    """Refuse an edit to a settled meal (its prep cycle locked)."""
    if policy.locked(date, mealtime):
        raise RuleError(
            f"{day_label(date)} {mealtime.value} is settled: its prep cycle "
            "ended (Admin can still change it)"
        )


def _check_planned(policy: Policy, session_date: datetime.date, what: str) -> None:
    """Refuse a change to the batches of a cooked session."""
    if not policy.session_open(session_date):
        raise RuleError(
            f"The {day_label(session_date)} session is already cooked: "
            f"{what} is Admin only"
        )


def _item(session: PrepSessionDTO, recipe_id: str) -> SessionItemDTO | None:
    return next((i for i in session.items if i.recipe == recipe_id), None)


def _week_of(draft: _Draft, week: str) -> DiaryWeekDTO:
    dto = draft.week(week)
    if dto is None:
        raise entries.EntryNotFoundError(f"No entries in week {week}")
    return dto


def _session_of(draft: _Draft, entry: DiaryEntryDTO) -> PrepSessionDTO | None:
    """The session a meal belongs to; ``None`` for takeout, for a recipe
    meal without one (older files) and when the session is gone."""
    if not isinstance(entry, RecipeEntryDTO) or entry.session is None:
        return None
    return draft.sessions.get(entry.session)


# ---------------------------------------------------------------------------
# Meals
# ---------------------------------------------------------------------------


def add_entry(
    diary: Diary,
    policy: Policy,
    week: str,
    date: datetime.date,
    mealtime: Mealtime,
    recipe: Recipe,
    position: int | None = None,
    session: uuid.UUID | None = None,
) -> tuple[Change, RecipeEntryDTO]:
    """Cook one more batch of ``recipe`` and put one portion on a day; the
    batch's other portions go to the unassigned slot.

    The batch is added to ``session`` when given, otherwise to the session
    on the meal's cycle day (``cycle_day``), created when that day has none.
    Refused when that session is already cooked (Admin adds to any)."""
    _check_open(policy, date, mealtime)
    draft = _Draft(diary, policy)
    if session is not None:
        target = draft.session(session)
        if target.date > date:
            raise RuleError(
                f"{recipe.title} on {day_label(date)} can't come from the "
                f"later {day_label(target.date)} session"
            )
    else:
        target_date = cycle_day(date, mealtime)
        found = draft.session_on(target_date)
        if found is None:
            _check_planned(policy, target_date, "adding a batch")
            found = PrepSessionDTO(
                id=uuid.uuid4(), date=target_date, items=[freeze_item(recipe)]
            )
            draft.put_session(found)
            entry = _spawn(draft, found, recipe.id)
            return _place_new(draft, week, date, mealtime, position, entry)
        target = found
    _check_planned(policy, target.date, "adding a batch")
    item = _item(target, recipe.id)
    if item is None:
        items = [*target.items, freeze_item(recipe)]
    else:
        items = [
            i.model_copy(update={"batches": i.batches + 1}) if i is item else i
            for i in target.items
        ]
    target = target.model_copy(update={"items": items})
    draft.put_session(target)
    entry = _spawn(draft, target, recipe.id)
    return _place_new(draft, week, date, mealtime, position, entry)


def _spawn(draft: _Draft, session: PrepSessionDTO, recipe_id: str) -> RecipeEntryDTO:
    """Make the meals of one new batch: all but one go to the unassigned
    slot; the one returned is for the caller to place."""
    item = _item(session, recipe_id)
    assert item is not None
    made = [portion_entry(item, session.id) for _ in range(item.servings)]
    if len(made) > 1:
        draft.put_unassigned([*draft.unassigned, *made[1:]])
    return made[0]


def _place_new(
    draft: _Draft,
    week: str,
    date: datetime.date,
    mealtime: Mealtime,
    position: int | None,
    entry: RecipeEntryDTO,
) -> tuple[Change, RecipeEntryDTO]:
    dto, _ = entries.insert_entry(
        draft.week(week), week, date, mealtime, entry, position
    )
    draft.put_week(week, dto)
    draft.check([entry.session])
    return draft.change(), entry


def take_unassigned(
    diary: Diary,
    policy: Policy,
    recipe_id: str,
    date: datetime.date,
    mealtime: Mealtime,
    position: int | None = None,
) -> Change:
    """Put one unassigned portion of ``recipe_id`` on a day: the one from
    the latest session on or before that day. Refused when there is none."""
    _check_open(policy, date, mealtime)
    draft = _Draft(diary, policy)
    found: list[tuple[datetime.date, RecipeEntryDTO]] = []
    for meal in draft.unassigned:
        session = _session_of(draft, meal)
        if meal.recipe == recipe_id and session is not None:
            found.append((session.date, meal))
    if not found:
        raise RuleError(f"There is no unassigned portion of '{recipe_id}'")
    fitting = [f for f in found if f[0] <= date]
    if not fitting:
        first, meal = min(found, key=lambda f: f[0])
        raise RuleError(
            f"The unassigned {meal.title} is cooked on {day_label(first)}: "
            f"it can't be eaten on {day_label(date)}"
        )
    _, meal = max(fitting, key=lambda f: f[0])
    return _move(draft, meal.id, Day(date, mealtime, position))


def move_meal(diary: Diary, policy: Policy, entry_id: uuid.UUID, to: Place) -> Change:
    """Move one meal to a day, the unassigned slot or the bin, from wherever
    it is. Its session never changes. A day before its session's date is
    refused, as is a settled day (either end) outside Admin; only meals of
    a prep session go to a slot."""
    return _move(_Draft(diary, policy), entry_id, to)


def remove_entry(
    diary: Diary, policy: Policy, week: str, entry_id: uuid.UUID
) -> Change:
    """Take one meal off its day (unless settled). A portion of a prep
    session goes to the unassigned slot: it only disappears with its batch.
    Takeout, and a recipe meal without a session, is deleted."""
    draft = _Draft(diary, policy)
    current = _week_of(draft, week)
    date, mealtime, entry = entries.find_entry(current, entry_id)
    if _session_of(draft, entry) is not None:
        return _move(draft, entry_id, "unassigned")
    _check_open(policy, date, mealtime)
    draft.put_week(week, entries.remove_entry(current, entry_id))
    return draft.change()


def _move(draft: _Draft, entry_id: uuid.UUID, to: Place) -> Change:
    policy = draft.policy
    entry: DiaryEntryDTO | None = None
    source_week: str | None = None
    for meal in draft.unassigned:
        if meal.id == entry_id:
            entry = meal
            if to == "unassigned":
                return Change()
            draft.put_unassigned(m for m in draft.unassigned if m.id != entry_id)
    for binned in draft.bin:
        if binned.id == entry_id:
            if to == "bin":
                return Change()
            # Out of the bin it is an ordinary meal again.
            entry = RecipeEntryDTO.model_validate(binned.model_dump(exclude={"binned"}))
            draft.put_bin(m for m in draft.bin if m.id != entry_id)
    if entry is None:
        for week, dto in draft.weeks.items():
            try:
                old_date, old_mealtime, entry = entries.find_entry(dto, entry_id)
            except entries.EntryNotFoundError:
                continue
            source_week = week
            _check_open(policy, old_date, old_mealtime)
            break
    if entry is None:
        raise entries.EntryNotFoundError(f"No meal {entry_id}")
    session = _session_of(draft, entry)

    if isinstance(to, Day):
        _check_open(policy, to.date, to.mealtime)
        if session is not None and to.date < session.date:
            raise RuleError(
                f"{entry.title} is cooked on {day_label(session.date)}: it "
                f"can't be eaten on {day_label(to.date)}"
            )
        target_week = week_id(to.date)
        if source_week == target_week:
            draft.put_week(
                target_week,
                entries.move_entry(
                    draft.weeks[target_week],
                    entry_id,
                    to.date,
                    to.mealtime,
                    to.position,
                ),
            )
        else:
            if source_week is not None:
                draft.put_week(
                    source_week,
                    entries.remove_entry(draft.weeks[source_week], entry_id),
                )
            dto, _ = entries.insert_entry(
                draft.week(target_week),
                target_week,
                to.date,
                to.mealtime,
                entry,
                to.position,
            )
            draft.put_week(target_week, dto)
        if isinstance(entry, RecipeEntryDTO) and entry.planned:
            # Placed by hand: the planner's pick becomes the person's.
            draft.put_week(
                target_week,
                entries.replace_entry(
                    draft.weeks[target_week],
                    entry.model_copy(update={"planned": None}),
                ),
            )
    else:
        if session is None or not isinstance(entry, RecipeEntryDTO):
            raise RuleError(
                f"{entry.title} is not a portion of a prep session: it can "
                "only be removed"
            )
        if source_week is not None:
            draft.put_week(
                source_week, entries.remove_entry(draft.weeks[source_week], entry_id)
            )
        if to == "unassigned":
            draft.put_unassigned([*draft.unassigned, entry])
        else:
            binned = BinnedEntryDTO.model_validate(
                {**entry.model_dump(), "binned": policy.today}
            )
            draft.put_bin([*draft.bin, binned])
    draft.check([session.id] if session is not None else [])
    return draft.change()


def add_takeout_entries(
    diary: Diary,
    policy: Policy,
    week: str,
    date: datetime.date,
    mealtime: Mealtime,
    added: Sequence[TakeoutEntryDTO],
    position: int | None = None,
) -> Change:
    """Add takeout entries to one slot, in order from ``position`` (``None``
    appends): a whole order at once. They never link to a session, so only
    the settled-meal lock applies."""
    _check_open(policy, date, mealtime)
    draft = _Draft(diary, policy)
    dto = draft.week(week)
    for offset, entry in enumerate(added):
        at = None if position is None else position + offset
        dto, _ = entries.insert_entry(dto, week, date, mealtime, entry, at)
    if dto is not None:
        draft.put_week(week, dto)
    return draft.change()


def edit_takeout_entry(
    diary: Diary, policy: Policy, week: str, entry: TakeoutEntryDTO
) -> Change:
    """Replace a takeout entry's title and numbers, keeping its id and
    place; recipe entries stay frozen."""
    draft = _Draft(diary, policy)
    current = _week_of(draft, week)
    date, mealtime, old = entries.find_entry(current, entry.id)
    _check_open(policy, date, mealtime)
    if not isinstance(old, TakeoutEntryDTO):
        raise RuleError(
            f"{old.title} is a recipe: its numbers are frozen (remove it and "
            "add it again)"
        )
    draft.put_week(week, entries.replace_entry(current, entry))
    return draft.change()


# ---------------------------------------------------------------------------
# Batches and sessions
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


def _without_item(session: PrepSessionDTO, recipe_id: str) -> PrepSessionDTO | None:
    """``session`` without one recipe line and its shopping ticks; ``None``
    when nothing is left."""
    items = [i for i in session.items if i.recipe != recipe_id]
    if not items:
        return None
    have = {r: ings for r, ings in session.have.items() if r != recipe_id}
    return session.model_copy(update={"items": items, "have": have})


def remove_batch(
    diary: Diary, policy: Policy, session_id: uuid.UUID, recipe_id: str
) -> Change:
    """Remove one batch of a recipe from a session that is still planned
    (Admin: any). The meals it no longer has portions for are taken from
    the unassigned slot; refused while too many are on days or in the bin.
    The last batch takes the recipe out of the session, and a session
    without recipes is deleted. This is the only way a portion disappears.
    """
    draft = _Draft(diary, policy)
    session, item = _session_item(draft, session_id, recipe_id)
    _check_planned(policy, session.date, "removing a batch")
    left = (item.batches - 1) * item.servings
    key = (session_id, recipe_id)
    free = slot_counts(draft.unassigned)[key]
    placed = draft.count(session_id, recipe_id) - free
    if placed > left:
        raise RuleError(
            f"{_plural(placed, 'meal')} of {item.title} are on days or in the "
            f"bin and {_plural(left, 'portion')} would be left: move "
            f"{placed - left} to unassigned first"
        )
    drop = max(0, placed + free - left)
    kept: list[RecipeEntryDTO] = []
    for meal in draft.unassigned:
        if drop and (meal.session, meal.recipe) == key:
            drop -= 1
        else:
            kept.append(meal)
    if len(kept) != len(draft.unassigned):
        draft.put_unassigned(kept)
    if item.batches > 1:
        # A planned batch goes first: removing a batch takes back the plan's.
        planned = item.planned_batches - 1 if item.planned_batches else None
        items = [
            i.model_copy(
                update={"batches": i.batches - 1, "planned_batches": planned or None}
            )
            if i is item
            else i
            for i in session.items
        ]
        draft.put_session(session.model_copy(update={"items": items}))
    else:
        rest = _without_item(session, recipe_id)
        if rest is None:
            draft.drop_session(session_id)
        else:
            draft.put_session(rest)
    return draft.change()


def move_item(
    diary: Diary,
    policy: Policy,
    session_id: uuid.UUID,
    recipe_id: str,
    to_session: uuid.UUID | None = None,
    to_date: datetime.date | None = None,
) -> Change:
    """Move a whole recipe line (every batch, every meal wherever it is) to
    ``to_session``, or to the session on ``to_date``, created when that day
    has none. Both sessions must still be planned (Admin: any), and no meal
    on a day may be before the new date. When the target already cooks the
    recipe the two lines merge: the batches add up and the target keeps its
    numbers. Shopping ticks move along unless the lines merge."""
    draft = _Draft(diary, policy)
    source, item = _session_item(draft, session_id, recipe_id)
    target: PrepSessionDTO | None
    if to_session is not None:
        target = draft.session(to_session)
    elif to_date is not None:
        target = draft.session_on(to_date)
    else:
        raise ValueError("Give the session or the day to move the recipe to")
    target_date = target.date if target is not None else to_date
    assert target_date is not None
    if target is not None and target.id == session_id:
        return Change()
    _check_planned(policy, source.date, "moving a recipe")
    _check_planned(policy, target_date, "moving a recipe")
    for link in linked_entries(draft.weeks.values()):
        if (link.session, link.entry.recipe) == (session_id, recipe_id) and (
            link.date < target_date
        ):
            raise RuleError(
                f"{item.title} on {day_label(link.date)} {link.mealtime.value} "
                f"is before {day_label(target_date)}: move that meal first"
            )

    ticks = source.have.get(recipe_id)
    if target is None:
        target = PrepSessionDTO(
            id=uuid.uuid4(),
            date=target_date,
            items=[item],
            have={recipe_id: ticks} if ticks else {},
        )
    else:
        existing = _item(target, recipe_id)
        if existing is None:
            have = {**target.have, recipe_id: ticks} if ticks else target.have
            target = target.model_copy(
                update={"items": [*target.items, item], "have": have}
            )
        else:
            planned = (existing.planned_batches or 0) + (item.planned_batches or 0)
            merged = existing.model_copy(
                update={
                    "batches": existing.batches + item.batches,
                    "planned_batches": planned or None,
                }
            )
            items = [merged if i is existing else i for i in target.items]
            target = target.model_copy(update={"items": items})
    draft.put_session(target)
    rest = _without_item(source, recipe_id)
    if rest is None:
        draft.drop_session(session_id)
    else:
        draft.put_session(rest)

    def relinked[T: RecipeEntryDTO](meals: Sequence[T]) -> list[T] | None:
        out = [
            m.model_copy(update={"session": target.id})
            if (m.session, m.recipe) == (session_id, recipe_id)
            else m
            for m in meals
        ]
        return out if out != list(meals) else None

    if (unassigned := relinked(draft.unassigned)) is not None:
        draft.put_unassigned(unassigned)
    if (binned := relinked(draft.bin)) is not None:
        draft.put_bin(binned)
    for week, dto in list(draft.weeks.items()):
        updated = dto
        for day in dto.days:
            for entry in day.entries():
                if isinstance(entry, RecipeEntryDTO) and (
                    entry.session,
                    entry.recipe,
                ) == (session_id, recipe_id):
                    updated = entries.set_entry_session(updated, entry.id, target.id)
        if updated is not dto:
            draft.put_week(week, updated)
    draft.check([target.id])
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
    draft = _Draft(diary, policy)
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
    every meal on a day must stay on or after the new date."""
    draft = _Draft(diary, policy)
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


# ---------------------------------------------------------------------------
# Planner (docs/planner.md)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PlannedCook:
    """Batches of a recipe the plan cooks in the session on ``session_date``."""

    session_date: datetime.date
    recipe_id: str
    batches: int


@dataclass(frozen=True, slots=True)
class PlannedMeal:
    """One portion the plan eats: a recipe of the session on
    ``session_date``, on a day and mealtime."""

    date: datetime.date
    mealtime: Mealtime
    recipe_id: str
    session_date: datetime.date


def apply_plan(
    diary: Diary,
    policy: Policy,
    recipes: Mapping[str, Recipe],
    cooks: Sequence[PlannedCook],
    meals: Sequence[PlannedMeal],
) -> Change:
    """Write a plan as one edit, every meal it places flagged ``planned``.

    Its batches go into the sessions on their days (created when a day has
    none), counted in the line's ``planned_batches``. A meal is first taken
    from the unassigned portions of its session's batch, then from the new
    portions; new portions the plan doesn't eat go to the unassigned slot.
    Meals go after what is on their day. Refused when a session it cooks in
    is cooked or a day is settled."""
    draft = _Draft(diary, policy)
    pools: dict[tuple[datetime.date, str], list[RecipeEntryDTO]] = {}
    stock: dict[tuple[datetime.date, str], list[RecipeEntryDTO]] = {}
    for unassigned in draft.unassigned:
        session = _session_of(draft, unassigned)
        if session is not None:
            stock.setdefault((session.date, unassigned.recipe), []).append(unassigned)
    by_session: dict[datetime.date, list[PlannedCook]] = {}
    for cook in cooks:
        if cook.batches > 0:
            by_session.setdefault(cook.session_date, []).append(cook)
    touched: list[uuid.UUID] = []
    for session_date, session_cooks in sorted(by_session.items()):
        _check_planned(policy, session_date, "planning")
        found = draft.session_on(session_date)
        session_id = found.id if found is not None else uuid.uuid4()
        items = list(found.items) if found is not None else []
        for cook in session_cooks:
            existing = next((i for i in items if i.recipe == cook.recipe_id), None)
            if existing is None:
                item = freeze_item(recipes[cook.recipe_id], cook.batches).model_copy(
                    update={"planned_batches": cook.batches}
                )
                items.append(item)
            else:
                item = existing
                items = [
                    i.model_copy(
                        update={
                            "batches": i.batches + cook.batches,
                            "planned_batches": (i.planned_batches or 0) + cook.batches,
                        }
                    )
                    if i is existing
                    else i
                    for i in items
                ]
            pools[(session_date, cook.recipe_id)] = [
                portion_entry(item, session_id).model_copy(update={"planned": True})
                for _ in range(cook.batches * item.servings)
            ]
        draft.put_session(
            PrepSessionDTO(
                id=session_id,
                date=session_date,
                items=items,
                have=found.have if found is not None else {},
            )
        )
        touched.append(session_id)
    taken: set[uuid.UUID] = set()
    for meal in meals:
        _check_open(policy, meal.date, meal.mealtime)
        key = (meal.session_date, meal.recipe_id)
        existing_portions = stock.get(key, [])
        if existing_portions:
            portion = existing_portions.pop(0)
            taken.add(portion.id)
            portion = portion.model_copy(update={"planned": True})
        elif pools.get(key):
            portion = pools[key].pop(0)
        else:
            raise RuleError(
                f"The plan eats more {meal.recipe_id} than the "
                f"{day_label(meal.session_date)} session has"
            )
        session = draft.session_on(meal.session_date)
        if session is not None and session.id not in touched:
            touched.append(session.id)
        week = week_id(meal.date)
        dto, _ = entries.insert_entry(
            draft.week(week), week, meal.date, meal.mealtime, portion
        )
        draft.put_week(week, dto)
    leftovers = [entry for pool in pools.values() for entry in pool]
    if taken or leftovers:
        draft.put_unassigned(
            [*(m for m in draft.unassigned if m.id not in taken), *leftovers]
        )
    draft.check(touched)
    return draft.change()


def clear_plans(diary: Diary, policy: Policy) -> Change:
    """Take every plan back, recipe line by recipe line.

    A planned session loses the batches the plan added (``planned_batches``)
    and up to that many portions of its planned meals, unassigned ones
    first; any other planned meal of the line was existing stock the plan
    placed, and goes back to the unassigned slot. The line keeps at least
    the batches its other meals need, a kept batch's spare portions go to
    the unassigned slot, a line with no batches goes and so does a session
    with no lines. A cooked session's batches are a fact: its planned meals
    all go back to the unassigned slot. Planned meals on days before today
    are history and stay."""
    draft = _Draft(diary, policy)
    # Planned meals on past days are history: they stay as they are.
    on_days: dict[tuple[uuid.UUID, str], list[tuple[str, RecipeEntryDTO]]] = {}
    for week, dto in draft.weeks.items():
        for day in dto.days:
            if day.date < policy.today:
                continue
            for entry in day.entries():
                if (
                    isinstance(entry, RecipeEntryDTO)
                    and entry.planned
                    and entry.session
                ):
                    on_days.setdefault((entry.session, entry.recipe), []).append(
                        (week, entry)
                    )
    slotted: dict[tuple[uuid.UUID, str], list[RecipeEntryDTO]] = {}
    for meal in draft.unassigned:
        if meal.planned and meal.session:
            slotted.setdefault((meal.session, meal.recipe), []).append(meal)

    drop_days: dict[str, list[uuid.UUID]] = {}
    drop_slot: set[uuid.UUID] = set()
    back: list[RecipeEntryDTO] = []  # placed stock going back, unflagged
    unflag_slot: set[uuid.UUID] = set()
    touched: list[uuid.UUID] = []
    new_items: dict[uuid.UUID, list[SessionItemDTO]] = {}
    refill: list[RecipeEntryDTO] = []
    for sid, session in list(draft.sessions.items()):
        planned_open = policy.session_open(session.date)
        items: list[SessionItemDTO] = []
        changed = False
        for item in session.items:
            key = (sid, item.recipe)
            days_ = on_days.get(key, [])
            slot_ = slotted.get(key, [])
            if not days_ and not slot_ and not item.planned_batches:
                items.append(item)
                continue
            changed = True
            own = (item.planned_batches or 0) * item.servings if planned_open else 0
            for meal in slot_:  # the plan's own portions go first from here
                if own:
                    drop_slot.add(meal.id)
                    own -= 1
                else:
                    unflag_slot.add(meal.id)
            for week, entry in days_:
                drop_days.setdefault(week, []).append(entry.id)
                if own:
                    own -= 1
                else:
                    back.append(entry.model_copy(update={"planned": None}))
            if not planned_open:
                items.append(item.model_copy(update={"planned_batches": None}))
                continue
            removed = len([m for m in slot_ if m.id in drop_slot]) + sum(
                1 for _, e in days_ if e.id not in {b.id for b in back}
            )
            meals_left = draft.count(sid, item.recipe) - removed
            kept_batches = max(
                item.batches - (item.planned_batches or 0),
                -(-meals_left // item.servings),
            )
            kept_batches = min(kept_batches, item.batches)
            if kept_batches == 0:
                continue
            kept = item.model_copy(
                update={"batches": kept_batches, "planned_batches": None}
            )
            items.append(kept)
            spare = kept_batches * item.servings - meals_left
            refill.extend(portion_entry(kept, sid) for _ in range(max(0, spare)))
        if changed:
            touched.append(sid)
            new_items[sid] = items

    for week, ids in drop_days.items():
        current: DiaryWeekDTO | None = draft.weeks[week]
        for entry_id in ids:
            assert current is not None
            current = entries.remove_entry(current, entry_id)
        draft.put_week(week, current)
    if drop_slot or unflag_slot or back or refill:
        draft.put_unassigned(
            [
                m.model_copy(update={"planned": None}) if m.id in unflag_slot else m
                for m in draft.unassigned
                if m.id not in drop_slot
            ]
            + back
            + refill
        )
    for sid in touched:
        items = new_items[sid]
        if items:
            draft.put_session(draft.sessions[sid].model_copy(update={"items": items}))
        else:
            draft.drop_session(sid)
    draft.check(touched)
    return draft.change()


def accept_session(diary: Diary, policy: Policy, session_id: uuid.UUID) -> Change:
    """Make a session's plan the person's own: the planned flag is cleared on
    its meals (on days and unassigned) and its batches (``planned_batches``)."""
    draft = _Draft(diary, policy)
    session = draft.session(session_id)  # must exist
    if any(i.planned_batches for i in session.items):
        draft.put_session(
            session.model_copy(
                update={
                    "items": [
                        i.model_copy(update={"planned_batches": None})
                        for i in session.items
                    ]
                }
            )
        )

    def flagged(entry: DiaryEntryDTO) -> bool:
        return (
            isinstance(entry, RecipeEntryDTO)
            and bool(entry.planned)
            and entry.session == session_id
        )

    for week, dto in list(draft.weeks.items()):
        current = dto
        changed = False
        for day in dto.days:
            for mealtime in Mealtime:
                for entry in getattr(day, mealtime.value) or ():
                    if flagged(entry):
                        current = entries.replace_entry(
                            current,
                            entry.model_copy(update={"planned": None}),
                        )
                        changed = True
        if changed:
            draft.put_week(week, current)
    if any(flagged(m) for m in draft.unassigned):
        draft.put_unassigned(
            m.model_copy(update={"planned": None}) if flagged(m) else m
            for m in draft.unassigned
        )
    return draft.change()
