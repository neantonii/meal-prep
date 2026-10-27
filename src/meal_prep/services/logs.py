"""Log enrichment service.

Turns a diary week DTO into the frozen ``LogWeek``. Entries keep logged order
and duplicates are preserved — every entry counts as one serving. No recipes
are needed: every entry already carries the numbers frozen when it was logged
(#107), so past weeks never change.
"""

from __future__ import annotations

from meal_prep.dtos.log import DiaryEntryDTO, DiaryWeekDTO
from meal_prep.enums import Mealtime
from meal_prep.models.ingredient import MacrosInfo
from meal_prep.models.log import LogDay, LogEntry, LogWeek


def diary_entry(entry: DiaryEntryDTO) -> LogEntry:
    """A diary entry: the numbers frozen when it was logged."""
    return LogEntry(
        recipe_id=entry.recipe,
        title=entry.title,
        cost=entry.cost,
        macros=MacrosInfo(
            calories_kcal=entry.calories_kcal,
            protein_g=entry.protein_g,
            fat_g=entry.fat_g,
            carbs_g=entry.carbs_g,
            fiber_g=entry.fiber_g,
            saturated_fat_g=entry.saturated_fat_g,
            sugars_g=entry.sugars_g,
            sodium_mg=entry.sodium_mg,
            potassium_mg=entry.potassium_mg,
        ),
        entry_id=str(entry.id),
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
