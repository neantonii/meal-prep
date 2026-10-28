"""Tests for the diary migration runner and migration 1."""

from __future__ import annotations

import datetime
import uuid
from pathlib import Path

import pytest
import yaml

from meal_prep.adapters.logs import save_diary_week
from meal_prep.adapters.sessions import load_session_file, save_session
from meal_prep.dtos.session import PrepSessionDTO
from meal_prep.enums import Mealtime
from meal_prep.library import load_library
from meal_prep.migrations import (
    MIGRATIONS,
    Migration,
    MigrationError,
    Migrator,
    m0001_session_packages,
    migrate,
)
from meal_prep.migrations.state import MigrationState
from meal_prep.models.library import Library
from meal_prep.services.diary import add_entry
from meal_prep.services.sessions import freeze_item, prepare_session

REPO = Path(__file__).resolve().parents[3]
CHICKEN = "air-fried-chicken-breast"


@pytest.fixture(scope="module")
def library() -> Library:
    return load_library(REPO / "data", REPO / "recipes")


def _old_session(diary: Path, library: Library) -> Path:
    """A session file as written before #152: no aisle, no package."""
    session = PrepSessionDTO(
        id=uuid.uuid4(),
        date=datetime.date(2026, 11, 1),
        items=[freeze_item(library.recipes[CHICKEN], batches=2)],
    )
    path = save_session(diary / "sessions", session)
    data = yaml.safe_load(path.read_text())
    for item in data["items"]:
        for line in item["ingredients"]:
            del line["aisle"], line["package"]
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path


def test_a_new_diary_is_marked_current_without_a_backup(
    tmp_path: Path, library: Library
):
    assert migrate(tmp_path, library) == []
    assert MigrationState(tmp_path).version == MIGRATIONS[-1].number
    assert not (tmp_path / ".backups").exists()


def test_old_sessions_are_backed_up_then_filled_in(tmp_path: Path, library: Library):
    path = _old_session(tmp_path, library)
    before = path.read_text()
    week, _ = add_entry(
        None,
        "2026-W45",
        datetime.date(2026, 11, 2),
        Mealtime.LUNCH,
        library.recipes[CHICKEN],
        None,
        None,
    )
    save_diary_week(tmp_path, week)
    assert migrate(tmp_path, library) == [1]
    [backup] = (tmp_path / ".backups").iterdir()
    assert backup.name.endswith("-before-0001")
    assert (backup / "sessions" / path.name).read_text() == before
    assert (backup / "2026-W45.yaml").exists()

    session = load_session_file(path)
    fresh = freeze_item(library.recipes[CHICKEN], batches=2)
    assert session.items[0].ingredients == fresh.ingredients
    needs = prepare_session(session).needs()
    assert all(group.aisle is not None for group in needs)

    state = yaml.safe_load((tmp_path / ".migrations.yaml").read_text())
    assert state["version"] == 1
    assert [h["number"] for h in state["history"]] == [1]
    # Up to date: nothing runs, no new backup.
    assert migrate(tmp_path, library) == []
    assert len(list((tmp_path / ".backups").iterdir())) == 1


def test_migration_1_is_idempotent_and_skips_unknown_ingredients(
    tmp_path: Path, library: Library
):
    path = _old_session(tmp_path, library)
    data = yaml.safe_load(path.read_text())
    data["items"][0]["ingredients"][0]["ingredient"] = "no-such-thing"
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    assert m0001_session_packages.apply(tmp_path, library) == 1
    once = path.read_text()
    assert m0001_session_packages.apply(tmp_path, library) == 0
    assert path.read_text() == once
    first = yaml.safe_load(once)["items"][0]["ingredients"][0]
    assert "aisle" not in first and "package" not in first


def test_a_failure_stops_with_the_backup_named(tmp_path: Path, library: Library):
    _old_session(tmp_path, library)

    def broken(diary: Path, lib: Library) -> int:
        raise ValueError("boom")

    migrator = Migrator(tmp_path, library, (Migration(1, "broken", broken),))
    with pytest.raises(MigrationError, match=r"boom.*\.backups"):
        migrator.run()
    assert MigrationState(tmp_path).version == 0  # retried on the next start


def test_data_newer_than_the_release_refuses_to_start(tmp_path: Path, library: Library):
    (tmp_path / ".migrations.yaml").write_text(
        f"version: {MIGRATIONS[-1].number + 1}\n"
    )
    with pytest.raises(MigrationError, match="older image"):
        migrate(tmp_path, library)
