"""The takeout API (#142): add, edit, repeats, and the week page."""

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
ORDER = {
    "title": "McDonald's McChicken",
    "kcal": 480,
    "protein_g": 16,
    "carbs_g": 45,
    "fat_g": 27,
}


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
    body = {"date": date, "mealtime": "lunch", "items": [{**ORDER, **fields}]}
    return _ok(client.post(f"/api/diary/{WEEK}/takeout", json=body))


def _entries(week: dict) -> list[dict]:
    return [e for d in week["days"] for m in d["meals"] for e in m["entries"]]


def test_add_a_whole_order_and_see_it_in_the_totals(client: TestClient):
    fries = {**ORDER, "title": "McDonald's Small Fries", "kcal": 230, "cost": 3.5}
    body = {"date": "2026-11-06", "mealtime": "lunch", "items": [ORDER, fries]}
    week = _ok(client.post(f"/api/diary/{WEEK}/takeout", json=body))
    chicken, fries_out = _entries(week)
    assert chicken["kind"] == fries_out["kind"] == "takeout"
    assert (chicken["kcal"], chicken["cost"]) == (480, None)
    assert "session" not in chicken and "recipe" not in chicken
    assert fries_out["cost"] == 3.5
    day = next(d for d in week["days"] if d["date"] == "2026-11-06")
    assert day["totals"]["kcal"] == 710 and day["totals"]["cost"] == 3.5
    assert all(s["id"] is None for s in week["sessions"])  # no session made


def test_recipe_entries_say_so(client: TestClient):
    body = {"date": "2026-11-06", "mealtime": "dinner", "recipe": "boiled-basmati-rice"}
    week = _ok(client.post(f"/api/diary/{WEEK}/entries", json=body))
    [rice] = _entries(week)
    assert rice["kind"] == "recipe" and rice["recipe"] == "boiled-basmati-rice"
    assert rice["session"] is not None and rice["cost"] > 0


def test_calories_and_macros_are_required(client: TestClient):
    body = {"date": "2026-11-06", "mealtime": "lunch", "items": [{"title": "Pho"}]}
    response = client.post(f"/api/diary/{WEEK}/takeout", json=body)
    assert response.status_code == 422


def test_edit_corrects_takeout_in_place_but_not_a_recipe(client: TestClient):
    [entry] = _entries(_add(client))
    body = {**ORDER, "kcal": 470, "fat_g": 21}
    week = _ok(client.put(f"/api/diary/{WEEK}/takeout/{entry['id']}", json=body))
    [edited] = _entries(week)
    assert edited["id"] == entry["id"]
    assert (edited["kcal"], edited["fat_g"]) == (470, 21)
    recipe = {
        "date": "2026-11-06",
        "mealtime": "dinner",
        "recipe": "boiled-basmati-rice",
    }
    rice = next(
        e
        for e in _entries(_ok(client.post(f"/api/diary/{WEEK}/entries", json=recipe)))
        if e["kind"] == "recipe"
    )
    response = client.put(f"/api/diary/{WEEK}/takeout/{rice['id']}", json=ORDER)
    assert response.status_code == 409 and "frozen" in response.json()["detail"]


def test_linking_takeout_is_refused(client: TestClient):
    [entry] = _entries(_add(client))
    response = client.put(
        f"/api/diary/{WEEK}/entries/{entry['id']}/session",
        json={"session_date": "2026-11-05"},
    )
    assert response.status_code == 409 and "never linked" in response.json()["detail"]


def test_usuals_list_past_meals_latest_first(client: TestClient, tmp_path: Path):
    assert _ok(client.get("/api/usuals")) == []
    _add(client)
    _add(client, date="2026-11-07", title="Large Pho with Brisket", kcal=780, cost=18.5)
    _add(client, date="2026-11-08", title="mcdonald's MCCHICKEN")
    usuals = _ok(client.get("/api/usuals"))
    assert [(u["title"], u["times"], u["last"]) for u in usuals] == [
        ("mcdonald's MCCHICKEN", 2, "2026-11-08"),
        ("Large Pho with Brisket", 1, "2026-11-07"),
    ]
    assert usuals[0]["kcal"] == 480 and usuals[1]["cost"] == 18.5
    # Every add is journaled.
    [month] = (tmp_path / "diary" / ".journal").glob("*.jsonl")
    actions = [json.loads(line)["action"] for line in month.read_text().splitlines()]
    assert actions == ["takeout.add"] * 3
