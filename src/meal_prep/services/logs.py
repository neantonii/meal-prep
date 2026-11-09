"""Log enrichment service.

Turns a diary week DTO into the frozen ``LogWeek``. Entries keep logged order
and duplicates are preserved — every entry counts as one serving. No recipes
are needed: every entry already carries the numbers frozen when it was logged
(#107), so past weeks never change.
"""

from __future__ import annotations

from meal_prep.dtos.log import DiaryEntryDTO, DiaryWeekDTO, RecipeEntryDTO
from meal_prep.enums import Mealtime
from meal_prep.models.ingredient import MacrosInfo
from meal_prep.models.log import (
    LogDay,
    LogEntry,
    LogWeek,
    RecipeLogEntry,
    TakeoutLogEntry,
)


def diary_entry(entry: DiaryEntryDTO) -> LogEntry:
    """A diary entry: the numbers frozen when it was logged (a takeout
    meal's unknown nutrients as 0)."""

    def number(name: str) -> float:
        value: float | None = getattr(entry, name)
        return 0.0 if value is None else value

    macros = MacrosInfo(
        calories_kcal=entry.calories_kcal,
        protein_g=entry.protein_g,
        fat_g=entry.fat_g,
        carbs_g=entry.carbs_g,
        fiber_g=number("fiber_g"),
        saturated_fat_g=number("saturated_fat_g"),
        sugars_g=number("sugars_g"),
        sodium_mg=number("sodium_mg"),
        potassium_mg=number("potassium_mg"),
    )
    if isinstance(entry, RecipeEntryDTO):
        return RecipeLogEntry(
            entry_id=str(entry.id),
            title=entry.title,
            macros=macros,
            recipe_id=entry.recipe,
            cost=entry.cost,
            session_id=None if entry.session is None else str(entry.session),
        )
    return TakeoutLogEntry(
        entry_id=str(entry.id), title=entry.title, macros=macros, cost=entry.cost
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
