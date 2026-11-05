"""The free-form entry API (#142): add, edit, repeats, and the week page."""

from __future__ import annotations

import datetime
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from meal_prep.server.app import create_app

REPO = Path(__file__).resolve().parents[3]
TODAY = datetime.date(2026, 11, 5)
WEEK = "2026-W45"
ORDER = {"title": "McChicken meal", "kcal": 1008, "protein_g": 35.2, "cost": 14}


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    app = create_app(
        REPO / "data", REPO / "recipes", tmp_path / "diary", today=lambda: TODAY
    )
    return TestClient(app)


def _ok(response) -> dict:
    assert response.status_code == 200, response.text
    return response.json()


def _add(client: TestClient, date: str = "2026-11-06", **fields) -> dict:
    body = {"date": date, "mealtime": "lunch", **ORDER, **fields}
    return _ok(client.post(f"/api/diary/{WEEK}/others", json=body))


def _entries(week: dict) -> list[dict]:
    return [e for d in week["days"] for m in d["meals"] for e in m["entries"]]


def _day(week: dict, date: str) -> dict:
    return next(d for d in week["days"] if d["date"] == date)


def test_add_a_half_eaten_estimate_and_see_it_in_the_totals(client: TestClient):
    week = _add(client, portion=0.5, estimated=True)
    [entry] = _entries(week)
    assert entry["recipe"] is None and entry["session"] is None
    assert (entry["kcal"], entry["cost"], entry["fat_g"]) == (504, 7, None)
    assert entry["portion"] == 0.5 and entry["estimated"]
    day = _day(week, "2026-11-06")
    assert day["totals"]["kcal"] == 504 and day["estimated"]
    assert day["unknown"] == ["carbs_g", "fat_g", "fiber_g"]
    assert week["estimated"] and week["unknown"] == day["unknown"]
    assert all(s["id"] is None for s in week["sessions"])  # no session made


def test_edit_corrects_the_numbers_in_place(client: TestClient):
    [entry] = _entries(_add(client))
    body = {**ORDER, "kcal": 1200, "fat_g": 52}
    week = _ok(client.put(f"/api/diary/{WEEK}/others/{entry['id']}", json=body))
    [edited] = _entries(week)
    assert edited["id"] == entry["id"]
    assert (edited["kcal"], edited["fat_g"], edited["estimated"]) == (1200, 52, False)
    # A recipe entry's numbers stay frozen.
    recipe = {
        "date": "2026-11-06",
        "mealtime": "dinner",
        "recipe": "boiled-basmati-rice",
    }
    rice = next(
        e
        for e in _entries(_ok(client.post(f"/api/diary/{WEEK}/entries", json=recipe)))
        if e["recipe"]
    )
    response = client.put(f"/api/diary/{WEEK}/others/{rice['id']}", json=ORDER)
    assert response.status_code == 409 and "frozen" in response.json()["detail"]


def test_linking_a_free_form_entry_is_refused(client: TestClient):
    [entry] = _entries(_add(client))
    response = client.put(
        f"/api/diary/{WEEK}/entries/{entry['id']}/session",
        json={"session_date": "2026-11-05"},
    )
    assert response.status_code == 409 and "never linked" in response.json()["detail"]


def test_usuals_list_past_meals_latest_first(client: TestClient, tmp_path: Path):
    assert _ok(client.get("/api/usuals")) == []
    _add(client, portion=0.5)
    _add(client, date="2026-11-07", title="Pho, large", kcal=780, cost=18.5)
    _add(client, date="2026-11-08", title="mcchicken MEAL", estimated=True)
    usuals = _ok(client.get("/api/usuals"))
    assert [(u["title"], u["times"], u["last"]) for u in usuals] == [
        ("mcchicken MEAL", 2, "2026-11-08"),
        ("Pho, large", 1, "2026-11-07"),
    ]
    assert usuals[0]["kcal"] == 1008 and usuals[0]["estimated"]
    # Both edits are journaled.
    [month] = (tmp_path / "diary" / ".journal").glob("*.jsonl")
    actions = [json.loads(line)["action"] for line in month.read_text().splitlines()]
    assert actions == ["other.add"] * 3
