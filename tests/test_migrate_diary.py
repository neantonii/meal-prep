"""Tests for the one-off diary migration (``scripts/migrate_diary.py``, #107)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from meal_prep.adapters.logs import load_diary_week

REPO = Path(__file__).resolve().parents[1]
_OLD = """\
week: 2026-W43
days:
  - date: 2026-10-19
    breakfast: [flat-white, flat-white]
    dinner: [boiled-roasted-buckwheat]
"""


def _run(monkeypatch: pytest.MonkeyPatch, diary: Path) -> None:
    spec = importlib.util.spec_from_file_location(
        "migrate_diary", REPO / "scripts" / "migrate_diary.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "migrate_diary.py",
            "--diary-dir",
            str(diary),
            "--data-dir",
            str(REPO / "data"),
            "--recipes-dir",
            str(REPO / "recipes"),
        ],
    )
    module.main()


def test_converts_old_weeks_and_keeps_a_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    (tmp_path / "2026-W43.yaml").write_text(_OLD)
    _run(monkeypatch, tmp_path)

    week = load_diary_week(tmp_path, "2026-W43")
    breakfast = week.days[0].breakfast
    assert breakfast is not None
    assert [e.recipe for e in breakfast] == ["flat-white", "flat-white"]
    assert breakfast[0].id != breakfast[1].id
    assert breakfast[0].calories_kcal > 0
    assert (tmp_path / "2026-W43.yaml.bak").read_text() == _OLD


def test_rerun_leaves_converted_weeks_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    (tmp_path / "2026-W43.yaml").write_text(_OLD)
    _run(monkeypatch, tmp_path)
    converted = (tmp_path / "2026-W43.yaml").read_text()
    _run(monkeypatch, tmp_path)
    assert (tmp_path / "2026-W43.yaml").read_text() == converted


def test_unknown_recipe_aborts_before_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    good = tmp_path / "2026-W43.yaml"
    good.write_text(_OLD)
    bad = tmp_path / "2026-W44.yaml"
    bad.write_text("week: 2026-W44\ndays:\n  - date: 2026-10-26\n    lunch: [nope]\n")
    with pytest.raises(ValueError, match="unknown recipe"):
        _run(monkeypatch, tmp_path)
    assert good.read_text() == _OLD
    assert not (tmp_path / "2026-W43.yaml.bak").exists()
