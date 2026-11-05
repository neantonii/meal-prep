"""Tests for the edit journal (``server/journal.py``) through the API."""

from __future__ import annotations

import datetime
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from meal_prep.server.app import create_app

REPO = Path(__file__).resolve().parents[3]
TODAY = datetime.date(2026, 11, 5)  # Thursday: a session day
WEEK = "2026-W45"
BEANS = "skillet-blistered-green-beans"  # 2 portions a batch


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    app = create_app(
        REPO / "data", REPO / "recipes", tmp_path / "diary", today=lambda: TODAY
    )
    return TestClient(app)


def _journal(tmp_path: Path) -> list[dict]:
    [month] = (tmp_path / "diary" / ".journal").glob("*.jsonl")
    return [json.loads(line) for line in month.read_text().splitlines()]


def _add(client: TestClient, date: str) -> dict:
    body = {"date": date, "mealtime": "lunch", "recipe": BEANS}
    response = client.post(f"/api/diary/{WEEK}/entries", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_each_edit_is_one_line_with_its_effects(client: TestClient, tmp_path: Path):
    _add(client, "2026-11-06")
    _add(client, "2026-11-07")
    week = _add(client, "2026-11-08")  # a third portion: a second batch
    sunday = next(
        e
        for d in week["days"]
        if d["date"] == "2026-11-08"
        for m in d["meals"]
        for e in m["entries"]
    )
    client.delete(f"/api/diary/{WEEK}/entries/{sunday['id']}")
    first, second, third, removed = _journal(tmp_path)

    assert first["action"] == "entry.add" and first["outcome"] == "ok"
    assert (first["today"], first["admin"]) == ("2026-11-05", False)
    assert first["params"]["session"] == "auto"
    [entry] = first["entries"]
    assert entry["before"] is None
    assert entry["after"]["session_date"] == "2026-11-05"
    [session] = first["sessions"]
    assert session["batches"] == {BEANS: [None, 1]}

    assert second["sessions"] == []  # a free portion: no batch changed
    assert third["sessions"][0]["batches"] == {BEANS: [1, 2]}
    assert removed["action"] == "entry.remove"
    assert removed["entries"][0]["after"] is None
    assert removed["sessions"][0]["batches"] == {BEANS: [2, 1]}


def test_refusals_are_journaled_with_their_message(client: TestClient, tmp_path: Path):
    week = _add(client, "2026-11-06")
    session = next(s for s in week["sessions"] if s["date"] == "2026-11-05")
    response = client.delete(
        f"/api/sessions/{session['id']}/items/{BEANS}", params={"week": WEEK}
    )
    assert response.status_code == 409
    record = _journal(tmp_path)[-1]
    assert (record["action"], record["outcome"]) == ("item.remove", "refused")
    assert "linked from Fri 6 Nov lunch" in record["message"]
    assert "entries" not in record  # nothing changed


def test_a_journal_that_cannot_be_written_never_fails_the_edit(
    client: TestClient, tmp_path: Path
):
    (tmp_path / "diary").mkdir(exist_ok=True)
    (tmp_path / "diary" / ".journal").write_text("not a folder")
    _add(client, "2026-11-06")


def test_requests_rejected_before_the_edit_are_journaled(
    client: TestClient, tmp_path: Path
):
    body = {"date": "2026-11-06", "mealtime": "lunch", "recipe": "no-such-recipe"}
    assert client.post(f"/api/diary/{WEEK}/entries", json=body).status_code == 422
    bad_week = {**body, "recipe": BEANS}
    assert client.post("/api/diary/2026-W99/entries", json=bad_week).status_code == 422
    malformed = {"date": "2026-11-06", "mealtime": "brunch", "recipe": BEANS}
    assert client.post(f"/api/diary/{WEEK}/entries", json=malformed).status_code == 422
    unknown, week, request = _journal(tmp_path)
    assert (unknown["action"], unknown["outcome"]) == ("entry.add", "invalid")
    assert "no-such-recipe" in unknown["message"]
    assert (week["action"], week["params"]["week"]) == ("entry.add", "2026-W99")
    assert request["action"] == f"POST /api/diary/{WEEK}/entries"
    assert request["params"]["body"]["mealtime"] == "brunch"
    assert request["outcome"] == "invalid"
