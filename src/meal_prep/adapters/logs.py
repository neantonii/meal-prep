"""YAML adapter for weekly plans and diary entries (``plans/*.yaml``, ``diary/*.yaml``).

Plans and diary files are gitignored personal data, not authored repo content — but they go
through the same deserialization + shape-validation pipeline as every other
DTO. No cross-validation against prepared recipes happens here; that is
enrichment, and lives in a service.

The week-keyed API (``load_log_week`` / ``save_log_week`` / ``delete_log_week``)
is the primary interface: the caller passes an explicit directory and the
filename is derived from the week id. The path-based loaders below are thin
wrappers kept for the CLI.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path

from meal_prep.adapters._yaml import read_yaml, write_yaml
from meal_prep.dtos.log import LogWeekDTO


def _week_path(logs_dir: Path | str, week: str) -> Path:
    """Resolve ``logs_dir / <week>.yaml`` for an explicit directory."""
    return Path(logs_dir) / f"{week}.yaml"


def load_log_week(logs_dir: Path | str, week: str) -> LogWeekDTO:
    """Load and validate one weekly log by week id (e.g. ``2026-W43``)."""
    file_path = _week_path(logs_dir, week)
    log = load_log_file(file_path)
    if log.week != week:
        raise ValueError(
            f"Log week '{log.week}' does not match filename stem '{week}' in {file_path}"
        )
    return log


def save_log_week(logs_dir: Path | str, log: LogWeekDTO) -> Path:
    """Validate and atomically write one weekly log, returning the file path.

    Creates ``logs_dir`` when absent. Writes to a temp file + renames so a
    crash or validation error never leaves a half-written week file.
    """
    directory = Path(logs_dir)
    directory.mkdir(parents=True, exist_ok=True)
    target = _week_path(directory, log.week)
    payload = log.model_dump(mode="json", exclude_none=True)
    tmp = target.with_name(f".{target.name}.tmp")
    try:
        write_yaml(tmp, payload)
        os.replace(tmp, target)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise
    return target


def delete_log_week(logs_dir: Path | str, week: str) -> bool:
    """Delete one weekly log file; ``True`` when a file was removed."""
    target = _week_path(logs_dir, week)
    try:
        target.unlink()
    except FileNotFoundError:
        return False
    return True


def load_log_file(path: Path | str) -> LogWeekDTO:
    """Load and validate one weekly log file into its DTO."""
    file_path = Path(path)
    data = read_yaml(file_path, what="Log week")

    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML structure in {file_path}: expected a mapping")

    log = LogWeekDTO.model_validate(data)
    return log


def load_all_logs(logs_dir: Path | str) -> dict[str, LogWeekDTO]:
    """Load and validate all weekly log files and ensure week uniqueness."""
    directory = Path(logs_dir)
    if not directory.exists() or not directory.is_dir():
        raise FileNotFoundError(f"Logs directory not found: {directory}")

    logs: dict[str, LogWeekDTO] = {}
    for yaml_file in sorted(directory.glob("*.yaml")):
        log = load_log_file(yaml_file)
        if log.week in logs:
            raise ValueError(f"Duplicate log week '{log.week}' across multiple files!")
        logs[log.week] = log

    return logs
