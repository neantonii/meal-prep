"""Tests for server file logging (``meal_prep.server.logging``)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from meal_prep.server.app import create_app
from meal_prep.server.logging import LOGGER_NAME, configure_logging

REPO = Path(__file__).resolve().parents[3]


def test_configure_logging_writes_file(tmp_path: Path) -> None:
    log_file = configure_logging(tmp_path / "logs")
    assert log_file is not None
    logging.getLogger(LOGGER_NAME).info("hello-log")
    for handler in logging.getLogger(LOGGER_NAME).handlers:
        handler.flush()
    assert "hello-log" in log_file.read_text()


def test_configure_logging_idempotent(tmp_path: Path) -> None:
    first = configure_logging(tmp_path / "logs")
    before = len(logging.getLogger(LOGGER_NAME).handlers)
    second = configure_logging(tmp_path / "logs")
    assert first == second
    assert len(logging.getLogger(LOGGER_NAME).handlers) == before


def test_requests_are_logged(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    app = create_app(REPO / "data", REPO / "recipes", tmp_path / "diary")
    client = TestClient(app)
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        client.get("/api/health")
        client.get("/api/diary/nope")
    assert "GET /api/health -> 200" in caplog.text
    assert "GET /api/diary/nope -> 422" in caplog.text


def test_entry_changes_are_logged(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    app = create_app(REPO / "data", REPO / "recipes", tmp_path / "diary")
    client = TestClient(app)
    body = {
        "date": "2026-10-19",
        "mealtime": "dinner",
        "recipe": "boiled-roasted-buckwheat",
    }
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        week = client.post("/api/diary/2026-W43/entries", json=body).json()
        entry_id = week["days"][0]["meals"][0]["entries"][0]["id"]
        client.patch(
            f"/api/diary/2026-W43/entries/{entry_id}",
            json={"date": "2026-10-20", "mealtime": "lunch"},
        )
        client.delete(f"/api/diary/2026-W43/entries/{entry_id}")
    assert "added boiled-roasted-buckwheat to 2026-10-19 dinner" in caplog.text
    assert f"moved entry {entry_id} to 2026-10-20 lunch" in caplog.text
    assert f"removed entry {entry_id} from 2026-W43" in caplog.text
