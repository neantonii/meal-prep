"""The edit journal: one JSON line per diary edit, to investigate later how
the diary got into a state.

``<diary_dir>/.journal/<YYYY-MM>.jsonl`` (UTC month), append-only, never
pruned. It lives with the diary so backups carry it; the dot-folder keeps it
out of migration backups and every loader. Each line holds when and in which
mode the edit ran, what was asked, how it ended (a refusal keeps its
message) and what it changed: every entry whose place or link moved and
each session item whose batches changed, as before -> after counts. Only
the edit's own effects are written, never the diary's state. Writing it
never fails an edit: a write error is logged and the edit stands.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from meal_prep.dtos.log import DiaryWeekDTO, RecipeEntryDTO
from meal_prep.dtos.session import PrepSessionDTO
from meal_prep.enums import Mealtime
from meal_prep.services.prep import Change, Diary

logger = logging.getLogger("meal_prep.server")

JOURNAL_DIR = ".journal"

type Json = dict[str, Any]


class Journal:
    """Appends edit records under ``<diary_dir>/.journal``."""

    def __init__(self, diary_dir: Path) -> None:
        self.dir = Path(diary_dir) / JOURNAL_DIR

    def record(
        self,
        action: str,
        params: Mapping[str, Any],
        *,
        today: datetime.date,
        admin: bool,
        outcome: str,
        message: str | None = None,
        before: Diary | None = None,
        change: Change | None = None,
    ) -> None:
        """Append one record; ``before`` and ``change`` give the diff."""
        now = datetime.datetime.now(datetime.UTC)
        record: Json = {
            "at": now.isoformat(timespec="milliseconds"),
            "action": action,
            "params": dict(params),
            "today": today.isoformat(),
            "admin": admin,
            "version": os.environ.get("MEAL_PREP_VERSION", "dev"),
            "outcome": outcome,
        }
        if message is not None:
            record["message"] = message
        if before is not None and change is not None:
            sessions = {**before.sessions, **_kept(change.sessions)}
            record["entries"] = entry_changes(before, change, sessions)
            record["sessions"] = session_changes(before, change)
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            line = json.dumps(record, default=str, ensure_ascii=False)
            with (self.dir / f"{now:%Y-%m}.jsonl").open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            logger.exception("could not write the edit journal")


def _kept(
    sessions: Mapping[uuid.UUID, PrepSessionDTO | None],
) -> dict[uuid.UUID, PrepSessionDTO]:
    return {sid: s for sid, s in sessions.items() if s is not None}


def _placements(week: DiaryWeekDTO | None) -> dict[uuid.UUID, tuple[Any, ...]]:
    """Entry id -> (recipe, title, date, mealtime, session id); takeout has
    no recipe or session."""
    if week is None:
        return {}
    placed: dict[uuid.UUID, tuple[Any, ...]] = {}
    for day in week.days:
        for mealtime in Mealtime:
            for entry in getattr(day, mealtime.value) or ():
                recipe = isinstance(entry, RecipeEntryDTO)
                placed[entry.id] = (
                    entry.recipe if recipe else None,
                    entry.title,
                    day.date,
                    mealtime,
                    entry.session if recipe else None,
                )
    return placed


def _place(
    found: tuple[Any, ...] | None, sessions: Mapping[uuid.UUID, PrepSessionDTO]
) -> Json | None:
    if found is None:
        return None
    _, _, date, mealtime, session_id = found
    session = sessions.get(session_id) if session_id is not None else None
    return {
        "date": date.isoformat(),
        "meal": mealtime.value,
        "session": None if session_id is None else str(session_id),
        "session_date": None if session is None else session.date.isoformat(),
    }


def entry_changes(
    before: Diary, change: Change, sessions: Mapping[uuid.UUID, PrepSessionDTO]
) -> list[Json]:
    """Entries added, removed, moved or relinked by ``change``."""
    out: list[Json] = []
    for week, after_dto in change.weeks.items():
        old = _placements(before.weeks.get(week))
        new = _placements(after_dto)
        for entry_id in [*old, *(i for i in new if i not in old)]:
            was, now = old.get(entry_id), new.get(entry_id)
            if was == now:
                continue
            recipe, title = (now or was)[:2]  # type: ignore[index]
            out.append(
                {
                    "id": str(entry_id),
                    "recipe": recipe,
                    "title": title,
                    "before": _place(was, before.sessions),
                    "after": _place(now, sessions),
                }
            )
    return out


def session_changes(before: Diary, change: Change) -> list[Json]:
    """Session items whose batches changed (``None``: not in the session,
    so a session created or deleted shows every item), and session moves.
    Checklist ticks alone are left to the record's ``params``."""
    out: list[Json] = []
    for session_id, after in change.sessions.items():
        was = before.sessions.get(session_id)
        old = {} if was is None else {i.recipe: i.batches for i in was.items}
        new = {} if after is None else {i.recipe: i.batches for i in after.items}
        batches = {
            recipe: [old.get(recipe), new.get(recipe)]
            for recipe in [*old, *(r for r in new if r not in old)]
            if old.get(recipe) != new.get(recipe)
        }
        dates = [None if s is None else s.date.isoformat() for s in (was, after)]
        if not batches and dates[0] == dates[1]:
            continue
        record: Json = {
            "id": str(session_id),
            "date": dates[1] or dates[0],
            "batches": batches,
        }
        if None not in dates and dates[0] != dates[1]:
            record["moved_from"] = dates[0]
        out.append(record)
    return out
