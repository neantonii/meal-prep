"""Tests for the meal/log adapters (``adapters/meals.py``, ``adapters/logs.py``)."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from meal_prep.adapters.logs import (
    delete_diary_week,
    load_diary_week,
    save_diary_week,
)
from meal_prep.adapters.meals import load_all_meals, load_meal_file
from meal_prep.dtos.log import DiaryWeekDTO


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# meals
# ---------------------------------------------------------------------------


def test_load_meal_file_valid(tmp_path: Path):
    path = _write(
        tmp_path / "hearty.yaml",
        "id: hearty\ntitle: Hearty\nrecipes:\n  - oatmeal\n  - coffee\n",
    )
    meal = load_meal_file(path)
    assert meal.id == "hearty"
    assert meal.recipes == ["oatmeal", "coffee"]


def test_load_meal_file_rejects_id_mismatch(tmp_path: Path):
    path = _write(
        tmp_path / "hearty.yaml",
        "id: other\ntitle: Other\nrecipes:\n  - oatmeal\n",
    )
    with pytest.raises(ValueError, match="does not match filename stem"):
        load_meal_file(path)


def test_load_all_meals_rejects_duplicates(tmp_path: Path):
    _write(tmp_path / "same.yaml", "id: same\ntitle: A\nrecipes:\n  - oatmeal\n")
    sub = tmp_path / "sub"
    sub.mkdir()
    _write(sub / "same.yaml", "id: same\ntitle: B\nrecipes:\n  - oatmeal\n")
    with pytest.raises(ValueError, match="Duplicate meal ID"):
        load_all_meals(tmp_path)


def test_load_all_meals_missing_dir(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="Meals directory"):
        load_all_meals(tmp_path / "nope")


# ---------------------------------------------------------------------------
# diary
# ---------------------------------------------------------------------------


def _entry(recipe: str = "oatmeal") -> dict:
    return {
        "id": str(uuid.uuid4()),
        "recipe": recipe,
        "title": recipe.title(),
        "cost": 1.0 / 3.0,  # unrounded on purpose
        "calories_kcal": 310.123456789,
        "protein_g": 12.0,
        "fat_g": 8.0,
        "carbs_g": 45.0,
        "fiber_g": 6.0,
        "saturated_fat_g": 1.5,
        "sugars_g": 9.0,
        "sodium_mg": 120.0,
        "potassium_mg": 300.0,
    }


def _diary(week: str = "2026-W42", date: str = "2026-10-13") -> DiaryWeekDTO:
    return DiaryWeekDTO.model_validate(
        {"week": week, "days": [{"date": date, "dinner": [_entry(), _entry()]}]}
    )


def test_diary_round_trip_keeps_ids_and_raw_numbers(tmp_path: Path):
    diary = _diary()
    target = save_diary_week(tmp_path / "diary", diary)
    assert target == tmp_path / "diary" / "2026-W42.yaml"
    loaded = load_diary_week(tmp_path / "diary", "2026-W42")
    assert loaded == diary  # ids and unrounded floats survive YAML


def test_load_diary_week_rejects_stem_mismatch(tmp_path: Path):
    # A valid W43 week stored under a W42 file name.
    save_diary_week(tmp_path, _diary(week="2026-W43", date="2026-10-20"))
    (tmp_path / "2026-W43.yaml").rename(tmp_path / "2026-W42.yaml")
    with pytest.raises(ValueError, match="does not match filename stem"):
        load_diary_week(tmp_path, "2026-W42")


def test_load_diary_week_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="Log week file not found"):
        load_diary_week(tmp_path, "2026-W42")


def test_delete_diary_week(tmp_path: Path):
    save_diary_week(tmp_path, _diary())
    assert delete_diary_week(tmp_path, "2026-W42") is True
    assert delete_diary_week(tmp_path, "2026-W42") is False


@pytest.mark.parametrize(
    "week", ["../2026-W42", "2026-W42/../x", "/etc/passwd", "2026-W42\n", "2026-w42"]
)
def test_diary_week_ids_must_be_iso_week_ids(tmp_path: Path, week: str):
    for call in (
        lambda: load_diary_week(tmp_path, week),
        lambda: delete_diary_week(tmp_path, week),
    ):
        with pytest.raises(ValueError, match="Invalid week id"):
            call()
