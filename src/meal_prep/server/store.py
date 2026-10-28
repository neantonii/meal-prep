"""The whole diary — every week file and every session file — for the server.

Links between entries and prep sessions span weeks, so the rules need every
week and every session at once. Parsed files are cached by modification time
and size: a request re-reads only files that changed (including edits made
by hand while the server runs).
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from meal_prep.adapters.logs import (
    delete_diary_week,
    diary_week_files,
    load_diary_week,
    save_diary_week,
)
from meal_prep.adapters.sessions import (
    delete_session,
    load_session_file,
    save_session,
    session_files,
)
from meal_prep.dtos.log import DiaryWeekDTO
from meal_prep.dtos.session import PrepSessionDTO
from meal_prep.services.prep import Change, Diary

T = TypeVar("T")

type _Stamp = tuple[int, int]


class DiaryFileError(ValueError):
    """A diary or session file on disk is invalid."""


class DiaryStore:
    """Reads and writes the diary under one directory (sessions in
    ``<diary_dir>/sessions``)."""

    def __init__(self, diary_dir: Path) -> None:
        self.diary_dir = Path(diary_dir)
        self.sessions_dir = self.diary_dir / "sessions"
        self._cache: dict[Path, tuple[_Stamp, object]] = {}

    def _cached(self, path: Path, load: Callable[[Path], T]) -> T:
        stat = os.stat(path)
        stamp = (stat.st_mtime_ns, stat.st_size)
        hit = self._cache.get(path)
        if hit is not None and hit[0] == stamp:
            return hit[1]  # type: ignore[return-value]
        try:
            value = load(path)
        except ValueError as e:
            raise DiaryFileError(f"invalid diary file {path.name}: {e}") from e
        self._cache[path] = (stamp, value)
        return value

    def load(self) -> Diary:
        """Every week and every session as they are on disk now."""
        weeks: dict[str, DiaryWeekDTO] = {}
        for path in diary_week_files(self.diary_dir):
            weeks[path.stem] = self._cached(
                path, lambda p: load_diary_week(p.parent, p.stem)
            )
        sessions: dict[uuid.UUID, PrepSessionDTO] = {}
        for path in session_files(self.sessions_dir):
            session = self._cached(path, load_session_file)
            if session.id in sessions:
                raise DiaryFileError(
                    f"session {session.id} is in two files: "
                    f"{sessions[session.id].date}.yaml and {path.name}"
                )
            sessions[session.id] = session
        live = {*diary_week_files(self.diary_dir), *session_files(self.sessions_dir)}
        for stale in self._cache.keys() - live:
            self._cache.pop(stale, None)  # reads run in parallel threads
        return Diary(weeks=weeks, sessions=sessions)

    def apply(self, before: Diary, change: Change) -> None:
        """Write ``change`` made against ``before``.

        Order: sessions are written first, weeks next, sessions deleted (or
        moved off their old date) last. An interrupted edit can then leave a
        spare portion or a session in two files, never an entry that breaks a
        link rule.
        """
        # Our own writes must never be served from the cache.
        for week in change.weeks:
            self._cache.pop(self.diary_dir / f"{week}.yaml", None)
        for session_id, session in change.sessions.items():
            for dto in (before.sessions.get(session_id), session):
                if dto is not None:
                    self._cache.pop(self.sessions_dir / f"{dto.date}.yaml", None)
        stale_dates = []
        for session_id, session in change.sessions.items():
            old = before.sessions.get(session_id)
            if session is not None:
                save_session(self.sessions_dir, session)
                if old is not None and old.date != session.date:
                    stale_dates.append(old.date)
            elif old is not None:
                stale_dates.append(old.date)
        for week, week_dto in change.weeks.items():
            if week_dto is None:
                delete_diary_week(self.diary_dir, week)
            else:
                save_diary_week(self.diary_dir, week_dto)
        for date in stale_dates:
            delete_session(self.sessions_dir, date)
