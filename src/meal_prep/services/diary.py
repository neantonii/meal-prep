"""Diary editing — single-entry operations on a diary week (#107).

An entry's numbers are frozen exactly once, when it is added. Removing,
moving, reordering and (re)linking to a prep session never recompute them, so nothing here needs to match
old and new entries. Every operation returns a new, re-validated
``DiaryWeekDTO`` (or ``None`` when the week ends up empty); storage is the
caller's job.
"""

from __future__ import annotations

import datetime
import uuid

from meal_prep.dtos.log import DiaryDayDTO, DiaryEntryDTO, DiaryWeekDTO
from meal_prep.enums import Mealtime
from meal_prep.models.recipe import Recipe

# date -> mealtime -> entries, the editable form of a week.
type _Slots = dict[datetime.date, dict[Mealtime, list[DiaryEntryDTO]]]


class EntryNotFoundError(LookupError):
    """No entry with the given id in this week."""


def freeze_entry(recipe: Recipe, session: uuid.UUID | None = None) -> DiaryEntryDTO:
    """A new diary entry carrying ``recipe``'s current per-serving numbers,
    linked to prep session ``session`` when given."""
    macros = recipe.per_serving_macros
    return DiaryEntryDTO(
        id=uuid.uuid4(),
        session=session,
        recipe=recipe.id,
        title=recipe.title,
        cost=recipe.cost_per_portion,
        calories_kcal=macros.calories_kcal,
        protein_g=macros.protein_g,
        fat_g=macros.fat_g,
        carbs_g=macros.carbs_g,
        fiber_g=macros.fiber_g,
        saturated_fat_g=macros.saturated_fat_g,
        sugars_g=macros.sugars_g,
        sodium_mg=macros.sodium_mg,
        potassium_mg=macros.potassium_mg,
    )


def _slots(diary: DiaryWeekDTO | None) -> _Slots:
    slots: _Slots = {}
    for day in diary.days if diary is not None else ():
        slots[day.date] = {
            mealtime: list(getattr(day, mealtime.value))
            for mealtime in Mealtime
            if getattr(day, mealtime.value) is not None
        }
    return slots


def _build(week: str, slots: _Slots) -> DiaryWeekDTO | None:
    days: list[DiaryDayDTO] = []
    for date, meals in sorted(slots.items()):
        filled = {m.value: entries for m, entries in meals.items() if entries}
        if filled:
            days.append(DiaryDayDTO(date=date, **filled))
    if not days:
        return None
    # Re-validate the whole week: day order, days inside the week, unique ids.
    return DiaryWeekDTO.model_validate({"week": week, "days": days})


def _insert(
    slots: _Slots,
    date: datetime.date,
    mealtime: Mealtime,
    entry: DiaryEntryDTO,
    position: int | None,
) -> None:
    target = slots.setdefault(date, {}).setdefault(mealtime, [])
    if position is None:
        target.append(entry)
    else:
        target.insert(max(0, min(position, len(target))), entry)


def find_entry(
    diary: DiaryWeekDTO, entry_id: uuid.UUID
) -> tuple[datetime.date, Mealtime, DiaryEntryDTO]:
    """Where entry ``entry_id`` sits: its date, mealtime and the entry."""
    for day in diary.days:
        for mealtime in Mealtime:
            for entry in getattr(day, mealtime.value) or ():
                if entry.id == entry_id:
                    return day.date, mealtime, entry
    raise EntryNotFoundError(f"No entry {entry_id} in this week")


def _take(slots: _Slots, entry_id: uuid.UUID) -> DiaryEntryDTO:
    for meals in slots.values():
        for entries in meals.values():
            for index, entry in enumerate(entries):
                if entry.id == entry_id:
                    return entries.pop(index)
    raise EntryNotFoundError(f"No entry {entry_id} in this week")


def add_entry(
    diary: DiaryWeekDTO | None,
    week: str,
    date: datetime.date,
    mealtime: Mealtime,
    recipe: Recipe,
    position: int | None = None,
    session: uuid.UUID | None = None,
) -> tuple[DiaryWeekDTO, DiaryEntryDTO]:
    """Add a newly frozen entry for ``recipe``; return the week and entry.

    ``position`` is its index in the slot; ``None`` appends. ``session`` links
    the entry to a prep session (the link rules are ``services.prep``'s job).
    """
    entry = freeze_entry(recipe, session)
    slots = _slots(diary)
    _insert(slots, date, mealtime, entry, position)
    result = _build(week, slots)
    assert result is not None  # it holds at least the new entry
    return result, entry


def remove_entry(diary: DiaryWeekDTO, entry_id: uuid.UUID) -> DiaryWeekDTO | None:
    """Remove one entry; ``None`` when the week is left empty."""
    slots = _slots(diary)
    _take(slots, entry_id)
    return _build(diary.week, slots)


def move_entry(
    diary: DiaryWeekDTO,
    entry_id: uuid.UUID,
    date: datetime.date,
    mealtime: Mealtime,
    position: int | None = None,
) -> DiaryWeekDTO:
    """Move or reorder one entry, keeping its frozen numbers.

    ``position`` is the index in the destination slot after the entry has
    been taken out of its old place; ``None`` appends.
    """
    slots = _slots(diary)
    entry = _take(slots, entry_id)
    _insert(slots, date, mealtime, entry, position)
    result = _build(diary.week, slots)
    assert result is not None  # the moved entry is still in the week
    return result


def set_entry_session(
    diary: DiaryWeekDTO, entry_id: uuid.UUID, session: uuid.UUID | None
) -> DiaryWeekDTO:
    """Link one entry to prep session ``session`` (``None`` unlinks it),
    keeping its place and its frozen numbers."""
    slots = _slots(diary)
    for meals in slots.values():
        for entries in meals.values():
            for index, entry in enumerate(entries):
                if entry.id == entry_id:
                    entries[index] = entry.model_copy(update={"session": session})
                    result = _build(diary.week, slots)
                    assert result is not None
                    return result
    raise EntryNotFoundError(f"No entry {entry_id} in this week")
