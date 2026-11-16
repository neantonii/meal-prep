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
    take = {"date": "2026-11-07", "mealtime": "lunch", "recipe": BEANS}
    assert client.post(f"/api/diary/{WEEK}/unassigned", json=take).status_code == 200
    week = _add(client, "2026-11-08")  # a drop never uses what exists: a batch
    sunday = next(
        e
        for d in week["days"]
        if d["date"] == "2026-11-08"
        for m in d["meals"]
        for e in m["entries"]
    )
    client.delete(f"/api/diary/{WEEK}/entries/{sunday['id']}")
    session = next(s for s in week["sessions"] if s["date"] == "2026-11-05")
    client.delete(
        f"/api/sessions/{session['id']}/items/{BEANS}/batch", params={"week": WEEK}
    )
    first, second, third, removed, batch = _journal(tmp_path)

    assert first["action"] == "entry.add" and first["outcome"] == "ok"
    assert (first["today"], first["admin"]) == ("2026-11-05", False)
    assert first["params"]["session"] is None
    # One portion on the day, the batch's other one unassigned.
    on_day, spare = sorted(first["entries"], key=lambda e: "slot" in e["after"])
    assert on_day["before"] is None and spare["before"] is None
    assert on_day["after"]["date"] == "2026-11-06"
    assert on_day["after"]["session_date"] == "2026-11-05"
    assert spare["after"]["slot"] == "unassigned"
    [made] = first["sessions"]
    assert made["batches"] == {BEANS: [None, 1]}

    assert second["action"] == "unassigned.take"
    assert second["sessions"] == []  # the portion existed: no batch changed
    [taken] = second["entries"]
    assert taken["id"] == spare["id"]
    assert taken["before"]["slot"] == "unassigned"
    assert taken["after"]["date"] == "2026-11-07"

    assert third["sessions"][0]["batches"] == {BEANS: [1, 2]}
    assert removed["action"] == "entry.remove"
    [unassigned] = removed["entries"]
    assert unassigned["before"]["date"] == "2026-11-08"
    assert unassigned["after"]["slot"] == "unassigned"
    assert removed["sessions"] == []  # the batch stays

    assert batch["action"] == "batch.remove"
    assert batch["sessions"][0]["batches"] == {BEANS: [2, 1]}
    assert [e["after"] for e in batch["entries"]] == [None, None]


def test_refusals_are_journaled_with_their_message(client: TestClient, tmp_path: Path):
    week = _add(client, "2026-11-06")
    session = next(s for s in week["sessions"] if s["date"] == "2026-11-05")
    response = client.delete(
        f"/api/sessions/{session['id']}/items/{BEANS}/batch", params={"week": WEEK}
    )
    assert response.status_code == 409
    record = _journal(tmp_path)[-1]
    assert (record["action"], record["outcome"]) == ("batch.remove", "refused")
    assert "move 1 to unassigned first" in record["message"]
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
