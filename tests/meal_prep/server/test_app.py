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


WEEK = "2026-W43"
BUCKWHEAT = "boiled-roasted-buckwheat"


def _add(client: TestClient, recipe: str = BUCKWHEAT, **where) -> dict:
    body = {"date": "2026-10-19", "mealtime": "dinner", "recipe": recipe, **where}
    r = client.post(f"/api/diary/{WEEK}/entries", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _slot(week: dict, day: int, mealtime: str) -> list[dict]:
    for meal in week["days"][day]["meals"]:
        if meal["mealtime"] == mealtime:
            return meal["entries"]
    return []


def test_missing_week_returns_scaffold(client: TestClient):
    body = client.get(f"/api/diary/{WEEK}").json()
    assert body["week"] == WEEK
    assert body["exists"] is False
    assert [d["date"] for d in body["days"]] == [
        f"2026-10-{day:02d}" for day in range(19, 26)
    ]
    assert all(d["meals"] == [] for d in body["days"])
    assert body["totals"]["kcal"] == 0


def test_add_entry_freezes_numbers_and_persists(client: TestClient, tmp_path: Path):
    week = _add(client)
    assert week["exists"] is True
    [entry] = _slot(week, 0, "dinner")
    assert entry["recipe"] == BUCKWHEAT
    assert entry["kcal"] > 0
    assert entry["card_url"] == f"/cards/recipe/modular_carb/{BUCKWHEAT}.html"
    assert week["totals"]["kcal"] == pytest.approx(entry["kcal"])
    assert week["days"][0]["totals"]["cost"] == pytest.approx(entry["cost"])

    saved = (tmp_path / "diary" / f"{WEEK}.yaml").read_text()
    assert entry["id"] in saved
    assert "calories_kcal" in saved
    assert client.get(f"/api/diary/{WEEK}").json() == week


def test_frozen_numbers_survive_a_server_with_changed_data(
    client: TestClient, tmp_path: Path
):
    _add(client)
    path = tmp_path / "diary" / f"{WEEK}.yaml"
    path.write_text(path.read_text().replace("title: ", "title: Old ", 1))
    # A fresh server (fresh library) still shows what was frozen.
    fresh = TestClient(create_app(REPO / "data", REPO / "recipes", tmp_path / "diary"))
    [entry] = _slot(fresh.get(f"/api/diary/{WEEK}").json(), 0, "dinner")
    assert entry["title"].startswith("Old ")


def test_add_unknown_recipe_rejected(client: TestClient, tmp_path: Path):
    r = client.post(
        f"/api/diary/{WEEK}/entries",
        json={"date": "2026-10-19", "mealtime": "dinner", "recipe": "nope"},
    )
    assert r.status_code == 422
    assert not (tmp_path / "diary" / f"{WEEK}.yaml").exists()


def test_add_rejects_bad_mealtime_and_out_of_week_date(client: TestClient):
    url = f"/api/diary/{WEEK}/entries"
    bad_meal = {"date": "2026-10-19", "mealtime": "brunch", "recipe": BUCKWHEAT}
    assert client.post(url, json=bad_meal).status_code == 422
    out_of_week = {"date": "2026-10-26", "mealtime": "dinner", "recipe": BUCKWHEAT}
    assert client.post(url, json=out_of_week).status_code == 422


def test_remove_entry_and_last_one_deletes_week(client: TestClient, tmp_path: Path):
    _add(client)
    week = _add(client)
    first, second = _slot(week, 0, "dinner")
    r = client.delete(f"/api/diary/{WEEK}/entries/{first['id']}")
    assert r.status_code == 200, r.text
    assert _slot(r.json(), 0, "dinner") == [second]
    r = client.delete(f"/api/diary/{WEEK}/entries/{second['id']}")
    assert r.json()["exists"] is False
    assert not (tmp_path / "diary" / f"{WEEK}.yaml").exists()


def test_remove_unknown_entry_404(client: TestClient):
    url = f"/api/diary/{WEEK}/entries/00000000-0000-4000-8000-000000000000"
    assert client.delete(url).status_code == 404
    _add(client)
    assert client.delete(url).status_code == 404
    assert client.delete(f"/api/diary/{WEEK}/entries/nope").status_code == 422


def test_move_entry_keeps_its_numbers(client: TestClient):
    [entry] = _slot(_add(client), 0, "dinner")
    r = client.patch(
        f"/api/diary/{WEEK}/entries/{entry['id']}",
        json={"date": "2026-10-21", "mealtime": "lunch"},
    )
    assert r.status_code == 200, r.text
    assert _slot(r.json(), 0, "dinner") == []
    assert _slot(r.json(), 2, "lunch") == [entry]


def test_reorder_within_slot(client: TestClient):
    _add(client, BUCKWHEAT)
    week = _add(client, "boiled-basmati-rice")
    first, second = _slot(week, 0, "dinner")
    r = client.patch(
        f"/api/diary/{WEEK}/entries/{second['id']}",
        json={"date": "2026-10-19", "mealtime": "dinner", "position": 0},
    )
    assert [e["id"] for e in _slot(r.json(), 0, "dinner")] == [
        second["id"],
        first["id"],
    ]


def test_move_out_of_week_rejected(client: TestClient):
    [entry] = _slot(_add(client), 0, "dinner")
    r = client.patch(
        f"/api/diary/{WEEK}/entries/{entry['id']}",
        json={"date": "2026-10-26", "mealtime": "dinner"},
    )
    assert r.status_code == 422


def test_corrupt_week_file_returns_422(client: TestClient, tmp_path: Path):
    diary = tmp_path / "diary"
    diary.mkdir(parents=True, exist_ok=True)
    (diary / f"{WEEK}.yaml").write_text(f"eek: {WEEK}\ndays: []\n")
    r = client.get(f"/api/diary/{WEEK}")
    assert r.status_code == 422
    assert "invalid diary file" in r.json()["detail"]


def test_old_format_week_asks_for_migration(client: TestClient, tmp_path: Path):
    diary = tmp_path / "diary"
    diary.mkdir(parents=True, exist_ok=True)
    (diary / f"{WEEK}.yaml").write_text(
        f"week: {WEEK}\ndays:\n  - date: 2026-10-19\n    dinner: [{BUCKWHEAT}]\n"
    )
    r = client.get(f"/api/diary/{WEEK}")
    assert r.status_code == 422
    assert "migrate_diary.py" in r.json()["detail"]


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
    for bad in ("nope", "2026-W43\n", "../2026-W43"):
        with pytest.raises(ValueError, match="Invalid week id"):
            week_dates(bad)


def test_week_with_trailing_newline_rejected(client: TestClient):
    assert client.get("/api/diary/2026-W43%0A").status_code == 422
