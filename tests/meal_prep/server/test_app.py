"""Tests for the diary server (``meal_prep.server``)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from meal_prep.server.app import create_app
from meal_prep.server.weeks import current_week, week_dates

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    app = create_app(REPO / "data", REPO / "recipes", tmp_path / "diary")
    return TestClient(app)


def test_health(client: TestClient):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_catalog_grouped(client: TestClient):
    body = client.get("/api/catalog").json()
    assert len(body["groups"]) == 6
    total = sum(len(g["recipes"]) for g in body["groups"])
    assert total > 0
    entry = body["groups"][0]["recipes"][0]
    assert {
        "id",
        "title",
        "category",
        "kcal",
        "protein_g",
        "carbs_g",
        "fat_g",
        "cost",
    } <= set(entry)


def test_missing_week_returns_scaffold(client: TestClient):
    body = client.get("/api/diary/2026-W43").json()
    assert body["week"] == "2026-W43"
    assert body["exists"] is False
    assert [d["date"] for d in body["days"]] == [
        f"2026-10-{day:02d}" for day in range(19, 26)
    ]
    assert all(d["meals"] == [] for d in body["days"])


def test_save_round_trip(client: TestClient, tmp_path: Path):
    payload = {
        "week": "2026-W43",
        "days": [{"date": "2026-10-19", "dinner": ["boiled-roasted-buckwheat"]}],
    }
    saved = client.post("/api/diary/2026-W43", json=payload)
    assert saved.status_code == 200, saved.text
    assert saved.json()["exists"] is True
    assert saved.json()["totals"]["kcal"] > 0
    assert (tmp_path / "diary" / "2026-W43.yaml").exists()

    loaded = client.get("/api/diary/2026-W43").json()
    assert loaded["exists"] is True
    assert loaded["days"][0]["meals"] == [
        {"mealtime": "dinner", "recipes": ["boiled-roasted-buckwheat"]}
    ]


def test_save_returns_full_week(client: TestClient):
    payload = {
        "week": "2026-W43",
        "days": [{"date": "2026-10-19", "dinner": ["boiled-roasted-buckwheat"]}],
    }
    saved = client.post("/api/diary/2026-W43", json=payload)
    assert saved.status_code == 200, saved.text
    days = saved.json()["days"]
    assert [d["date"] for d in days] == [f"2026-10-{day:02d}" for day in range(19, 26)]
    assert days[0]["meals"] == [
        {"mealtime": "dinner", "recipes": ["boiled-roasted-buckwheat"]}
    ]
    assert all(d["meals"] == [] for d in days[1:])


def test_save_unknown_recipe_rejected(client: TestClient, tmp_path: Path):
    payload = {
        "week": "2026-W43",
        "days": [{"date": "2026-10-19", "dinner": ["nope"]}],
    }
    r = client.post("/api/diary/2026-W43", json=payload)
    assert r.status_code == 422
    assert not (tmp_path / "diary" / "2026-W43.yaml").exists()


def test_delete_week(client: TestClient, tmp_path: Path):
    payload = {
        "week": "2026-W43",
        "days": [{"date": "2026-10-19", "dinner": ["boiled-roasted-buckwheat"]}],
    }
    client.post("/api/diary/2026-W43", json=payload)
    assert client.delete("/api/diary/2026-W43").status_code == 204
    assert client.delete("/api/diary/2026-W43").status_code == 204
    assert client.get("/api/diary/2026-W43").json()["exists"] is False


def test_recipe_and_ingredient_cards_served(client: TestClient):
    body = client.get("/api/catalog").json()
    rid = body["groups"][0]["recipes"][0]["id"]
    cat = body["groups"][0]["category"]
    r = client.get(f"/cards/recipe/{cat}/{rid}.html")
    assert r.status_code == 200
    assert "<html" in r.text
    assert client.get("/cards/recipe/nope/nope.html").status_code == 404


def test_week_dates():
    assert str(week_dates("2026-W43")[0]) == "2026-10-19"
    assert len(week_dates("2026-W43")) == 7
    assert current_week().startswith("20")
    with pytest.raises(ValueError, match="Invalid week id"):
        week_dates("nope")
