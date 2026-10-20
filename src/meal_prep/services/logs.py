"""Log enrichment service.

Turns an authored log-week DTO into the frozen, fully-resolved ``LogWeek``
value by resolving each mealtime's recipe ids against prepared recipes.
Entries keep authored order and duplicates are preserved — every entry counts
as one serving.

Log validation is deliberately trivial here: recipe enrichment already
guarantees sane cost/macros, so this service only checks that every logged
recipe exists.
"""

from __future__ import annotations

from collections.abc import Mapping

from meal_prep.dtos.log import LogWeekDTO
from meal_prep.enums import Mealtime
from meal_prep.models.log import LogDay, LogWeek
from meal_prep.models.recipe import Recipe


def prepare_log_week(log: LogWeekDTO, recipes: Mapping[str, Recipe]) -> LogWeek:
    """Resolve one authored log week into its frozen enriched value."""
    days: list[LogDay] = []
    for day_dto in log.days:
        resolved: dict[str, tuple[Recipe, ...]] = {}
        for mealtime in Mealtime:
            ids = getattr(day_dto, mealtime.value)
            if ids is None:
                continue
            entries: list[Recipe] = []
            for recipe_id in ids:
                recipe = recipes.get(recipe_id)
                if recipe is None:
                    raise ValueError(
                        f"Log week '{log.week}' day '{day_dto.date}' "
                        f"mealtime '{mealtime.value}' references "
                        f"unknown recipe '{recipe_id}'."
                    )
                entries.append(recipe)
            resolved[mealtime.value] = tuple(entries)
        days.append(LogDay(date=day_dto.date, **resolved))
    return LogWeek(week=log.week, days=tuple(days))
