"""Tests for the meal/log adapters (``adapters/meals.py``, ``adapters/logs.py``)."""

from __future__ import annotations

from pathlib import Path

import pytest

from meal_prep.adapters.logs import (
    delete_log_week,
    load_all_logs,
    load_log_file,
    load_log_week,
    save_log_week,
)
from meal_prep.adapters.meals import load_all_meals, load_meal_file
from meal_prep.dtos.log import LogWeekDTO


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
    dinner: [oatmeal]
    breakfast: [oatmeal, coffee]
"""


def test_load_log_file_valid(tmp_path: Path):
    path = _write(tmp_path / "2026-W42.yaml", _LOG)
    log = load_log_file(path)
    assert log.week == "2026-W42"
    assert log.days[0].breakfast == ["oatmeal", "coffee"]
    assert log.days[0].dinner == ["oatmeal"]
    assert log.days[0].lunch is None
    assert log.source_path == path


def test_load_all_logs_rejects_duplicate_weeks(tmp_path: Path):
    _write(tmp_path / "a.yaml", _LOG)
    _write(tmp_path / "b.yaml", _LOG)
    with pytest.raises(ValueError, match="Duplicate log week"):
        load_all_logs(tmp_path)


def test_load_all_logs_missing_dir(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="Logs directory"):
        load_all_logs(tmp_path / "nope")


def test_load_log_week_round_trip(tmp_path: Path):
    log = LogWeekDTO.model_validate(
        {
            "week": "2026-W42",
            "days": [{"date": "2026-10-13", "dinner": ["oatmeal", "oatmeal"]}],
        }
    )
    target = save_log_week(tmp_path / "diary", log)
    assert target == tmp_path / "diary" / "2026-W42.yaml"
    assert log.source_path == target
    loaded = load_log_week(tmp_path / "diary", "2026-W42")
    assert loaded.week == "2026-W42"
    assert loaded.days[0].dinner == ["oatmeal", "oatmeal"]


def test_load_log_week_rejects_stem_mismatch(tmp_path: Path):
    _write(tmp_path / "2026-W42.yaml", _LOG.replace("2026-W42", "2026-W43"))
    with pytest.raises(ValueError, match="does not match filename stem"):
        load_log_week(tmp_path, "2026-W42")


def test_load_log_week_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="Log week file not found"):
        load_log_week(tmp_path, "2026-W42")


def test_save_log_week_creates_dir(tmp_path: Path):
    log = LogWeekDTO.model_validate(
        {"week": "2026-W42", "days": [{"date": "2026-10-13", "dinner": ["oatmeal"]}]}
    )
    target = save_log_week(tmp_path / "new" / "diary", log)
    assert target.exists()


def test_delete_log_week(tmp_path: Path):
    log = LogWeekDTO.model_validate(
        {"week": "2026-W42", "days": [{"date": "2026-10-13", "dinner": ["oatmeal"]}]}
    )
    save_log_week(tmp_path, log)
    assert delete_log_week(tmp_path, "2026-W42") is True
    assert delete_log_week(tmp_path, "2026-W42") is False
