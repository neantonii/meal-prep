"""Tests for single-entry diary editing (``services/diary.py``, #107)."""

from __future__ import annotations

import datetime
import uuid

import pytest

from meal_prep.dtos.log import DiaryWeekDTO
from meal_prep.enums import Aisle, Mealtime, RecipeCategory, StorageType
from meal_prep.models.ingredient import MacrosInfo, Package
from meal_prep.models.recipe import Recipe, RecipeIngredient
from meal_prep.services.diary import (
    EntryNotFoundError,
    add_entry,
    freeze_entry,
    move_entry,
    remove_entry,
)

WEEK = "2026-W42"
MON = datetime.date(2026, 10, 12)
TUE = datetime.date(2026, 10, 13)


def _recipe(recipe_id: str, *, cost: float = 1.0, cal: float = 100.0) -> Recipe:
    macros = MacrosInfo(cal, 10.0, 5.0, 20.0, 1.0, 2.0, 3.0, 40.0, 50.0)
    return Recipe(
        id=recipe_id,
        title=f"Recipe {recipe_id}",
        category=RecipeCategory.BREAKFAST,
        servings=1.0,
        cooked_g=300.0,
        fridge_days=3,
        freezer_friendly=False,
        equipment=(),
        cookware_by_token={},
        ingredients=(
            RecipeIngredient(
                id="a",
                name="A",
                step_name="a",
                aisle=Aisle.PANTRY,
                storage=StorageType.AMBIENT,
                shelf_life_days=30,
                quantity=100.0,
                unit="g",
                grams=100.0,
                cost=cost,
                macros=macros,
                package=Package("Test 1 kg", 1.0, "kg", 1000.0),
            ),
        ),
        instructions="Cook.",
    )


def _slot(week: DiaryWeekDTO, date: datetime.date, mealtime: Mealtime) -> list[str]:
    for day in week.days:
        if day.date == date:
            return [e.recipe for e in getattr(day, mealtime.value) or []]
    return []


def test_freeze_entry_copies_all_numbers():
    entry = freeze_entry(_recipe("oats", cost=1.5, cal=250.0))
    assert isinstance(entry.id, uuid.UUID)
    assert (entry.recipe, entry.title, entry.cost) == ("oats", "Recipe oats", 1.5)
    assert entry.calories_kcal == 250.0
    assert (entry.sodium_mg, entry.potassium_mg) == (40.0, 50.0)


def test_add_entry_creates_week_and_appends():
    week, first = add_entry(None, WEEK, TUE, Mealtime.LUNCH, _recipe("a"))
    week, _ = add_entry(week, WEEK, TUE, Mealtime.LUNCH, _recipe("b"))
    week, _ = add_entry(week, WEEK, MON, Mealtime.DINNER, _recipe("c"))
    assert _slot(week, TUE, Mealtime.LUNCH) == ["a", "b"]
    assert [d.date for d in week.days] == [MON, TUE]  # days stay in date order
    assert week.days[1].lunch is not None
    assert week.days[1].lunch[0].id == first.id


def test_add_entry_at_position():
    week, _ = add_entry(None, WEEK, TUE, Mealtime.LUNCH, _recipe("a"))
    week, _ = add_entry(week, WEEK, TUE, Mealtime.LUNCH, _recipe("b"), position=0)
    assert _slot(week, TUE, Mealtime.LUNCH) == ["b", "a"]


def test_add_entry_rejects_date_outside_week():
    with pytest.raises(ValueError, match="outside ISO week"):
        add_entry(None, WEEK, datetime.date(2026, 10, 19), Mealtime.LUNCH, _recipe("a"))


def test_remove_entry_and_empty_week():
    week, a = add_entry(None, WEEK, TUE, Mealtime.LUNCH, _recipe("a"))
    week, b = add_entry(week, WEEK, TUE, Mealtime.LUNCH, _recipe("b"))
    after = remove_entry(week, a.id)
    assert after is not None
    assert _slot(after, TUE, Mealtime.LUNCH) == ["b"]
    assert remove_entry(after, b.id) is None


def test_remove_unknown_entry():
    week, _ = add_entry(None, WEEK, TUE, Mealtime.LUNCH, _recipe("a"))
    with pytest.raises(EntryNotFoundError):
        remove_entry(week, uuid.uuid4())


def test_move_keeps_frozen_numbers_and_drops_empty_day():
    week, entry = add_entry(None, WEEK, TUE, Mealtime.LUNCH, _recipe("a", cost=2.0))
    moved = move_entry(week, entry.id, MON, Mealtime.DINNER)
    assert [d.date for d in moved.days] == [MON]
    assert moved.days[0].dinner == [entry]  # same id, same numbers


def test_reorder_within_a_slot():
    week = None
    ids = []
    for name in ("a", "b", "c"):
        week, entry = add_entry(week, WEEK, TUE, Mealtime.LUNCH, _recipe(name))
        ids.append(entry.id)
    assert week is not None
    week = move_entry(week, ids[2], TUE, Mealtime.LUNCH, position=0)
    assert _slot(week, TUE, Mealtime.LUNCH) == ["c", "a", "b"]
    week = move_entry(week, ids[2], TUE, Mealtime.LUNCH, position=99)
    assert _slot(week, TUE, Mealtime.LUNCH) == ["a", "b", "c"]


def test_move_into_position_of_another_slot():
    week, a = add_entry(None, WEEK, TUE, Mealtime.LUNCH, _recipe("a"))
    week, _ = add_entry(week, WEEK, MON, Mealtime.DINNER, _recipe("b"))
    week = move_entry(week, a.id, MON, Mealtime.DINNER, position=0)
    assert _slot(week, MON, Mealtime.DINNER) == ["a", "b"]


def test_move_rejects_date_outside_week():
    week, a = add_entry(None, WEEK, TUE, Mealtime.LUNCH, _recipe("a"))
    with pytest.raises(ValueError, match="outside ISO week"):
        move_entry(week, a.id, datetime.date(2026, 10, 19), Mealtime.LUNCH)
