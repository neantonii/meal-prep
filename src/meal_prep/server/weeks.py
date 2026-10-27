"""Week-id <-> date mapping for scaffolding new diary weeks."""

from __future__ import annotations

import datetime

from meal_prep.dtos.log import WEEK_ID


def week_dates(week: str) -> tuple[datetime.date, ...]:
    """Return the 7 dates (Mon..Sun) for an ISO week id like ``2026-W43``."""
    match = WEEK_ID.fullmatch(week)
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
