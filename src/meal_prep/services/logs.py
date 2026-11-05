"""Log enrichment service.

Turns a diary week DTO into the frozen ``LogWeek``. Entries keep logged order
and duplicates are preserved — every entry counts as one serving. No recipes
are needed: every entry already carries the numbers frozen when it was logged
(#107), so past weeks never change.
"""

from __future__ import annotations

from meal_prep.dtos.log import NUMBERS, DiaryEntryDTO, DiaryWeekDTO
from meal_prep.enums import Mealtime
from meal_prep.models.ingredient import MacrosInfo
from meal_prep.models.log import EntryEstimate, LogDay, LogEntry, LogWeek


def diary_entry(entry: DiaryEntryDTO) -> LogEntry:
    """A diary entry: the numbers frozen when it was logged (unknown ones of
    a free-form entry as 0, named in ``unknown``)."""

    def number(name: str) -> float:
        value: float | None = getattr(entry, name)
        return 0.0 if value is None else value

    estimate = entry.estimate
    return LogEntry(
        recipe_id=entry.recipe,
        title=entry.title,
        cost=number("cost"),
        macros=MacrosInfo(
            calories_kcal=number("calories_kcal"),
            protein_g=number("protein_g"),
            fat_g=number("fat_g"),
            carbs_g=number("carbs_g"),
            fiber_g=number("fiber_g"),
            saturated_fat_g=number("saturated_fat_g"),
            sugars_g=number("sugars_g"),
            sodium_mg=number("sodium_mg"),
            potassium_mg=number("potassium_mg"),
        ),
        entry_id=str(entry.id),
        session_id=str(entry.session) if entry.session is not None else None,
        unknown=frozenset(n for n in NUMBERS if getattr(entry, n) is None),
        portion=entry.portion,
        estimate=None
        if estimate is None
        else EntryEstimate(
            source=estimate.source,
            kcal_low=estimate.kcal_low,
            kcal_high=estimate.kcal_high,
            assumptions=tuple(estimate.assumptions),
        ),
    )


def prepare_diary_week(diary: DiaryWeekDTO) -> LogWeek:
    """Build a diary week from its frozen entries (no recipe lookup)."""
    days: list[LogDay] = []
    for day_dto in diary.days:
        resolved: dict[str, tuple[LogEntry, ...]] = {}
        for mealtime in Mealtime:
            entries = getattr(day_dto, mealtime.value)
            if entries is not None:
                resolved[mealtime.value] = tuple(diary_entry(e) for e in entries)
        days.append(LogDay(date=day_dto.date, **resolved))
    return LogWeek(week=diary.week, days=tuple(days))
