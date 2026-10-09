"""Tests for the meal/log adapters (``adapters/meals.py``, ``adapters/logs.py``)."""

from __future__ import annotations

from pathlib import Path

import pytest

from meal_prep.adapters.logs import load_all_logs, load_log_file
from meal_prep.adapters.meals import load_all_meals, load_meal_file
from meal_prep.enums import Mealtime


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
    assert meal.source_path == path


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
# logs
# ---------------------------------------------------------------------------

_LOG = """\
week: 2026-W42
days:
  - date: 2026-10-13
    slots:
      - mealtime: dinner
        recipes: [oatmeal]
      - mealtime: breakfast
        recipes: [oatmeal, coffee]
"""


def test_load_log_file_valid(tmp_path: Path):
    path = _write(tmp_path / "2026-W42.yaml", _LOG)
    log = load_log_file(path)
    assert log.week == "2026-W42"
    assert [s.mealtime for s in log.days[0].slots] == [
        Mealtime.BREAKFAST,
        Mealtime.DINNER,
    ]
    assert log.source_path == path


def test_load_all_logs_rejects_duplicate_weeks(tmp_path: Path):
    _write(tmp_path / "a.yaml", _LOG)
    _write(tmp_path / "b.yaml", _LOG)
    with pytest.raises(ValueError, match="Duplicate log week"):
        load_all_logs(tmp_path)


def test_load_all_logs_missing_dir(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="Logs directory"):
        load_all_logs(tmp_path / "nope")
