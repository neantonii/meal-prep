"""YAML adapter for prep sessions (``diary/sessions/<YYYY-MM-DD>.yaml``).

Session files are gitignored personal data, like diary weeks. One file per
session, named by its date (at most one session per day); the caller passes
an explicit directory. Saving a session under a new date does not remove the
old file: moving a session is the caller's save-then-delete.
"""

from __future__ import annotations

import datetime
import os
from pathlib import Path
from typing import Any

from meal_prep.adapters._yaml import read_yaml, write_yaml_atomic
from meal_prep.dtos.session import PrepSessionDTO


def _session_path(sessions_dir: Path | str, date: datetime.date) -> Path:
    """``sessions_dir / <date>.yaml``; the name comes from a real date only."""
    base = os.path.normpath(os.path.abspath(sessions_dir))
    return Path(base) / f"{date.isoformat()}.yaml"


def _file_date(path: Path) -> datetime.date | None:
    try:
        return datetime.date.fromisoformat(path.stem)
    except ValueError:
        return None


def session_files(sessions_dir: Path | str) -> list[Path]:
    """All session files in ``sessions_dir`` (``YYYY-MM-DD.yaml``), by date."""
    directory = Path(sessions_dir)
    if not directory.is_dir():
        return []
    return sorted(
        path
        for path in directory.glob("*.yaml")
        if len(path.stem) == 10 and _file_date(path) is not None
    )


def load_session_file(path: Path | str) -> PrepSessionDTO:
    """Load and validate one session file; its date must match its name."""
    file_path = Path(path)
    data: Any = read_yaml(file_path, what="Prep session")
    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML structure in {file_path}: expected a mapping")
    session = PrepSessionDTO.model_validate(data)
    if session.date.isoformat() != file_path.stem:
        raise ValueError(
            f"Session date {session.date} does not match filename stem "
            f"'{file_path.stem}' in {file_path}"
        )
    return session


def save_session(sessions_dir: Path | str, session: PrepSessionDTO) -> Path:
    """Validate and atomically write one session file, returning its path.

    Creates ``sessions_dir`` when absent.
    """
    directory = Path(sessions_dir)
    directory.mkdir(parents=True, exist_ok=True)
    target = _session_path(directory, session.date)
    return write_yaml_atomic(target, session.model_dump(mode="json", exclude_none=True))


def delete_session(sessions_dir: Path | str, date: datetime.date) -> bool:
    """Delete the session file of ``date``; ``True`` when a file was removed."""
    try:
        _session_path(sessions_dir, date).unlink()
    except FileNotFoundError:
        return False
    return True
