"""The whole diary — every week file, every session file and the two slots
without a date — for the server.

Links between entries and prep sessions span weeks, so the rules need every
week, every session and both slots at once. Parsed files are cached by modification time
and size: a request re-reads only files that changed (including edits made
by hand while the server runs).
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from functools import partial
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
from meal_prep.adapters.slots import (
    BIN_FILE,
    UNASSIGNED_FILE,
    load_bin,
    load_unassigned,
    save_bin,
    save_unassigned,
)
from meal_prep.adapters.staples import STAPLES_FILE, load_staples, save_staples
from meal_prep.dtos.log import DiaryWeekDTO
from meal_prep.dtos.session import PrepSessionDTO
from meal_prep.dtos.slots import BinDTO, UnassignedDTO
from meal_prep.dtos.staples import StaplesDTO
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
        live = {
            *diary_week_files(self.diary_dir),
            *session_files(self.sessions_dir),
            *(self.diary_dir / n for n in (UNASSIGNED_FILE, BIN_FILE, STAPLES_FILE)),
        }
        for stale in self._cache.keys() - live:
            self._cache.pop(stale, None)  # reads run in parallel threads
        return Diary(
            weeks=weeks,
            sessions=sessions,
            unassigned=tuple(self._slot(UNASSIGNED_FILE, load_unassigned).meals),
            bin=tuple(self._slot(BIN_FILE, load_bin).meals),
        )

    def _slot[S: (UnassignedDTO, BinDTO)](
        self, name: str, load: Callable[[Path], S]
    ) -> S:
        """One of the slot files; a missing one is empty."""
        path = self.diary_dir / name
        if not path.exists():
            return load(path)
        return self._cached(path, load)

    def load_staples(self) -> StaplesDTO:
        """The ingredients always on hand (``staples.yaml``; none if absent)."""
        path = self.diary_dir / STAPLES_FILE
        if not path.exists():
            return StaplesDTO()
        return self._cached(path, load_staples)

    def save_staples(self, staples: StaplesDTO) -> None:
        path = self.diary_dir / STAPLES_FILE
        self._cache.pop(path, None)
        save_staples(path, staples)

    def apply(self, before: Diary, change: Change) -> None:
        """Write ``change`` made against ``before``.

        The one hard rule is that an item never has more meals than
        portions, so an interrupted edit must lose a meal or leave a portion
        without one, never the opposite. Order: sessions that keep or gain
        portions; then the meal files (weeks and the two slots), those that
        lose meals before those that gain them; then sessions that lose
        portions; sessions deleted (or moved off their old date) last.
        """
        # Our own writes must never be served from the cache.
        for week in change.weeks:
            self._cache.pop(self.diary_dir / f"{week}.yaml", None)
        for name in (UNASSIGNED_FILE, BIN_FILE):
            self._cache.pop(self.diary_dir / name, None)
        for session_id, session in change.sessions.items():
            for dto in (before.sessions.get(session_id), session):
                if dto is not None:
                    self._cache.pop(self.sessions_dir / f"{dto.date}.yaml", None)

        def portions(session: PrepSessionDTO | None) -> int:
            if session is None:
                return 0
            return sum(i.batches * i.servings for i in session.items)

        stale_dates = []
        shrunk: list[PrepSessionDTO] = []
        for session_id, session in change.sessions.items():
            old = before.sessions.get(session_id)
            if session is not None:
                if portions(session) < portions(old):
                    shrunk.append(session)
                else:
                    save_session(self.sessions_dir, session)
                if old is not None and old.date != session.date:
                    stale_dates.append(old.date)
            elif old is not None:
                stale_dates.append(old.date)

        def meals(week: DiaryWeekDTO | None) -> int:
            return 0 if week is None else sum(len(d.entries()) for d in week.days)

        writes: list[tuple[int, Callable[[], object]]] = []
        for week, week_dto in change.weeks.items():
            gained = meals(week_dto) - meals(before.weeks.get(week))
            if week_dto is None:
                writes.append(
                    (gained, partial(delete_diary_week, self.diary_dir, week))
                )
            else:
                writes.append(
                    (gained, partial(save_diary_week, self.diary_dir, week_dto))
                )
        if change.unassigned is not None:
            slot = UnassignedDTO(meals=list(change.unassigned))
            path = self.diary_dir / UNASSIGNED_FILE
            gained = len(change.unassigned) - len(before.unassigned)
            writes.append((gained, partial(save_unassigned, path, slot)))
        if change.bin is not None:
            binned = BinDTO(meals=list(change.bin))
            gained = len(change.bin) - len(before.bin)
            writes.append(
                (gained, partial(save_bin, self.diary_dir / BIN_FILE, binned))
            )
        for _, write in sorted(writes, key=lambda w: w[0]):
            write()

        for session in shrunk:
            save_session(self.sessions_dir, session)
        for date in stale_dates:
            delete_session(self.sessions_dir, date)
