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


def test_save_is_logged(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    app = create_app(REPO / "data", REPO / "recipes", tmp_path / "diary")
    client = TestClient(app)
    payload = {
        "week": "2026-W43",
        "days": [{"date": "2026-10-19", "dinner": ["boiled-roasted-buckwheat"]}],
    }
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        client.post("/api/diary/2026-W43", json=payload)
        client.delete("/api/diary/2026-W43")
    assert "saved week 2026-W43 (1 recipes)" in caplog.text
    assert "deleted week 2026-W43 (existed=True)" in caplog.text
