"""Week-id <-> date mapping for scaffolding new diary weeks."""

from __future__ import annotations

import datetime
import re

_WEEK_RE = re.compile(r"^(\d{4})-W(\d{2})$")


def week_dates(week: str) -> tuple[datetime.date, ...]:
    """Return the 7 dates (Mon..Sun) for an ISO week id like ``2026-W43``."""
    match = _WEEK_RE.match(week)
    if match is None:
        raise ValueError(f"Invalid week id '{week}': expected YYYY-Www")
    year, num = int(match.group(1)), int(match.group(2))
    try:
        monday = datetime.date.fromisocalendar(year, num, 1)
    except ValueError as e:
        raise ValueError(f"Invalid week id '{week}': {e}") from e
    return tuple(monday + datetime.timedelta(days=i) for i in range(7))


def current_week(today: datetime.date | None = None) -> str:
    """Return the ISO week id for ``today`` (default: local date)."""
    day = today or datetime.date.today()
    year, num, _ = day.isocalendar()
    return f"{year}-W{num:02d}"


def _temp_type_error() -> int:
    return "not an int"
