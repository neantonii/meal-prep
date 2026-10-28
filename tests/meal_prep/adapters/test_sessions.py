"""Tests for the prep session adapter (``adapters/sessions.py``)."""

from __future__ import annotations

import datetime
import uuid
from pathlib import Path

import pytest

from meal_prep.adapters.logs import diary_week_files
from meal_prep.adapters.sessions import (
    delete_session,
    load_session_file,
    save_session,
    session_files,
)
from meal_prep.dtos.session import PrepSessionDTO, SessionItemDTO

SUN = datetime.date(2026, 11, 1)


def _session(date: datetime.date = SUN) -> PrepSessionDTO:
    item = SessionItemDTO(
        recipe="rice",
        title="Rice",
        batches=1,
        servings=3,
        cost=0.5,
        calories_kcal=200.0,
        protein_g=4.0,
        fat_g=1.0,
        carbs_g=44.0,
        fiber_g=1.0,
        saturated_fat_g=0.0,
        sugars_g=0.0,
        sodium_mg=1.0,
        potassium_mg=50.0,
        ingredients=[],
    )
    return PrepSessionDTO(id=uuid.uuid4(), date=date, items=[item])


def test_save_load_round_trip_and_delete(tmp_path: Path):
    sessions = tmp_path / "sessions"
    session = _session()
    path = save_session(sessions, session)
    assert path == sessions / "2026-11-01.yaml"
    assert load_session_file(path) == session
    assert session_files(sessions) == [path]
    assert delete_session(sessions, SUN) is True
    assert delete_session(sessions, SUN) is False
    assert session_files(sessions) == []


def test_load_rejects_a_date_that_does_not_match_the_name(tmp_path: Path):
    path = save_session(tmp_path, _session())
    moved = path.rename(tmp_path / "2026-11-03.yaml")
    with pytest.raises(ValueError, match="does not match"):
        load_session_file(moved)


def test_listings_skip_other_files(tmp_path: Path):
    assert session_files(tmp_path / "missing") == []
    for name in ("notes.yaml", "2026-13-01.yaml", ".2026-11-01.yaml.tmp"):
        (tmp_path / name).write_text("x: 1\n")
    (tmp_path / "2026-W45.yaml").write_text("x: 1\n")
    save_session(tmp_path, _session())
    assert [p.name for p in session_files(tmp_path)] == ["2026-11-01.yaml"]
    assert [p.name for p in diary_week_files(tmp_path)] == ["2026-W45.yaml"]
