"""Log enrichment service.

Turns an authored log-week DTO into the frozen, fully-resolved ``LogWeek``
value by resolving each slot's recipe ids against prepared recipes. Entries
keep authored order and duplicates are preserved — every entry counts as one
serving.

Log validation is deliberately trivial here: recipe enrichment already
guarantees sane cost/macros, so this service only checks that every logged
recipe exists.
"""

from __future__ import annotations

from collections.abc import Mapping

from meal_prep.dtos.log import LogWeekDTO
from meal_prep.models.log import LogDay, LoggedSlot, LogWeek
from meal_prep.models.recipe import Recipe


def prepare_log_week(log: LogWeekDTO, recipes: Mapping[str, Recipe]) -> LogWeek:
    """Resolve one authored log week into its frozen enriched value."""
    days: list[LogDay] = []
    for day_dto in log.days:
        slots: list[LoggedSlot] = []
        for slot_dto in day_dto.slots:
            resolved: list[Recipe] = []
            for recipe_id in slot_dto.recipes:
                recipe = recipes.get(recipe_id)
                if recipe is None:
                    raise ValueError(
                        f"Log week '{log.week}' day '{day_dto.date}' "
                        f"slot '{slot_dto.mealtime.value}' references "
                        f"unknown recipe '{recipe_id}'."
                    )
                resolved.append(recipe)
            slots.append(
                LoggedSlot(mealtime=slot_dto.mealtime, recipes=tuple(resolved))
            )
        days.append(LogDay(date=day_dto.date, slots=tuple(slots)))
    return LogWeek(week=log.week, days=tuple(days), source_path=log.source_path)
