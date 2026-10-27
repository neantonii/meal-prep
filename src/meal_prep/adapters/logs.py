"""YAML adapter for the diary (``diary/*.yaml``).

Diary files are gitignored personal data, not authored repo content, but they
go through the same deserialization + shape-validation pipeline as every
other DTO. The diary is week-keyed (``load_diary_week`` / ``save_diary_week`` /
``delete_diary_week``): the caller passes an explicit directory and the file
name is derived from the week id. ``load_diary_file`` loads one by path for
the CLI.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import Any

from meal_prep.adapters._yaml import read_yaml, write_yaml
from meal_prep.dtos.log import WEEK_ID, DiaryWeekDTO
from meal_prep.enums import Mealtime


def _week_path(diary_dir: Path | str, week: str) -> Path:
    """Resolve ``diary_dir / <week>.yaml`` for an explicit directory.

    The week id becomes a file name, so it is checked here, not only by
    callers: anything but ``YYYY-Www`` (no separators, no ``..``, no trailing
    newline) is rejected before a path is built.
    """
    if WEEK_ID.fullmatch(week) is None:
        raise ValueError(f"Invalid week id {week!r}: expected YYYY-Www")
    # Belt and braces: whatever the id rule becomes, the file stays inside
    # the diary directory.
    base = os.path.normpath(os.path.abspath(diary_dir))
    path = os.path.normpath(os.path.join(base, f"{week}.yaml"))
    if not path.startswith(base + os.sep):
        raise ValueError(f"Week file for {week!r} is outside {base}")
    return Path(path)


def _read_week(file_path: Path) -> dict[str, Any]:
    data = read_yaml(file_path, what="Log week")
    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML structure in {file_path}: expected a mapping")
    return data


def _has_bare_recipe_ids(data: dict[str, Any]) -> bool:
    """True when any mealtime lists plain recipe ids (the pre-#107 format)."""
    days = data.get("days")
    if not isinstance(days, list):
        return False
    return any(
        isinstance(item, str)
        for day in days
        if isinstance(day, dict)
        for mealtime in Mealtime
        if isinstance(day.get(mealtime.value), list)
        for item in day[mealtime.value]
    )


def load_diary_file(path: Path | str) -> DiaryWeekDTO:
    """Load and validate one diary week file into its DTO."""
    file_path = Path(path)
    data = _read_week(file_path)
    if _has_bare_recipe_ids(data):
        raise ValueError(
            f"{file_path} lists bare recipe ids: it is a diary week from before "
            "entries carried frozen numbers. Convert old weeks once with "
            "scripts/migrate_diary.py."
        )
    return DiaryWeekDTO.model_validate(data)


def load_diary_week(diary_dir: Path | str, week: str) -> DiaryWeekDTO:
    """Load and validate one diary week by week id (e.g. ``2026-W43``)."""
    file_path = _week_path(diary_dir, week)
    diary = load_diary_file(file_path)
    if diary.week != week:
        raise ValueError(
            f"Log week '{diary.week}' does not match filename stem '{week}' "
            f"in {file_path}"
        )
    return diary


def save_diary_week(diary_dir: Path | str, diary: DiaryWeekDTO) -> Path:
    """Validate and atomically write one diary week, returning the file path.

    Creates ``diary_dir`` when absent. Writes to a temp file + renames so a
    crash or validation error never leaves a half-written week file.
    """
    directory = Path(diary_dir)
    directory.mkdir(parents=True, exist_ok=True)
    target = _week_path(directory, diary.week)
    payload = diary.model_dump(mode="json", exclude_none=True)
    tmp = target.with_name(f".{target.name}.tmp")
    try:
        write_yaml(tmp, payload)
        os.replace(tmp, target)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise
    return target


def delete_diary_week(diary_dir: Path | str, week: str) -> bool:
    """Delete one diary week file; ``True`` when a file was removed."""
    target = _week_path(diary_dir, week)
    try:
        target.unlink()
    except FileNotFoundError:
        return False
    return True
