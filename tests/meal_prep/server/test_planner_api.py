"""Tests for the planner API (``server/planner_routes.py``,
``docs/planner.md``) against the real recipe library."""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from meal_prep.server.app import create_app
from tests.meal_prep.server.test_sessions_api import CHICKEN, REPO, _add, _ok

TODAY = datetime.date(2026, 11, 5)  # Thursday: Thursday's session is planned
W45, W46 = "2026-W45", "2026-W46"


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    app = create_app(
        REPO / "data", REPO / "recipes", tmp_path / "diary", today=lambda: TODAY
    )
    return TestClient(app)


def _meals(week: dict) -> list[tuple[str, str, dict]]:
    return [
        (d["date"], m["mealtime"], e)
        for d in week["days"]
        for m in d["meals"]
        for e in m["entries"]
    ]


def _plan(client: TestClient, week: str = W45) -> dict:
    return _ok(client.post("/api/plan", params={"week": week}))


def test_plan_fills_the_week_ahead_with_flagged_meals(client: TestClient):
    week = _plan(client)
    planned = [(d, m) for d, m, e in _meals(week) if e.get("planned")]
    # From Thursday's dinner on: Thu dinner and snacks, then Fri-Sun.
    assert ("2026-11-05", "dinner") in planned
    assert ("2026-11-05", "lunch") not in planned  # Tuesday's cycle
    assert {d for d, _ in planned} == {f"2026-11-0{n}" for n in (5, 6, 7, 8)}
    # The plan continues into next week (7 days from Thursday: to Wednesday).
    next_week = _ok(client.get(f"/api/diary/{W46}"))
    assert {d for d, _, e in _meals(next_week) if e.get("planned")} == {
        "2026-11-09",
        "2026-11-10",
        "2026-11-11",
    }
    sessions = {s["date"] for s in week["sessions"] if s.get("id")}
    assert {"2026-11-05", "2026-11-08"} <= sessions


def test_plan_completes_a_half_filled_meal(client: TestClient):
    # Chicken by hand on Friday's dinner: the plan keeps it and adds a carb
    # and a salad around it, nothing else.
    _ok(_add(client, "2026-11-06", CHICKEN, mealtime="dinner"))
    week = _plan(client)
    friday_dinner = [
        e for d, m, e in _meals(week) if (d, m) == ("2026-11-06", "dinner")
    ]
    assert (CHICKEN, False) in [(e["recipe"], e.get("planned")) for e in friday_dinner]
    added = [e for e in friday_dinner if e.get("planned")]
    assert len(added) == 2
    # Chicken is already eaten on Friday: the plan doesn't repeat it that day.
    friday = [e["recipe"] for d, _, e in _meals(week) if d == "2026-11-06"]
    assert friday.count(CHICKEN) == 1


def test_plan_leaves_a_takeout_meal_alone(client: TestClient):
    takeout = {"title": "Pho", "kcal": 700, "protein_g": 40, "fat_g": 15, "carbs_g": 90}
    _ok(
        client.post(
            f"/api/diary/{W45}/takeout",
            json={"date": "2026-11-06", "mealtime": "dinner", "items": [takeout]},
        )
    )
    week = _plan(client)
    friday_dinner = [
        e for d, m, e in _meals(week) if (d, m) == ("2026-11-06", "dinner")
    ]
    assert [e["kind"] for e in friday_dinner] == ["takeout"]


def test_plan_uses_unassigned_portions_first(client: TestClient):
    # A hand drop on Thursday dinner: 1 chicken on the day, 1 unassigned.
    _ok(_add(client, "2026-11-05", CHICKEN, mealtime="dinner"))
    week = _plan(client)
    assert all(u["recipe"] != CHICKEN for u in week["unassigned"])
    placed = [
        e
        for w in (W45, W46)
        for _, _, e in _meals(_ok(client.get(f"/api/diary/{w}")))
        if e["recipe"] == CHICKEN and e.get("planned")
    ]
    assert placed  # the existing portion, on some day of the week ahead
    # Clear plans puts the portion back.
    week = _ok(client.delete("/api/plan", params={"week": W45}))
    assert [u["count"] for u in week["unassigned"] if u["recipe"] == CHICKEN] == [1]


def test_clear_plans_takes_it_all_back(client: TestClient):
    _ok(_add(client, "2026-11-06", CHICKEN, mealtime="dinner"))
    before = _ok(client.get(f"/api/diary/{W45}"))
    _plan(client)
    week = _ok(client.delete("/api/plan", params={"week": W45}))
    assert _meals(week) == _meals(before)
    assert [s["date"] for s in week["sessions"] if s.get("id")] == [
        s["date"] for s in before["sessions"] if s.get("id")
    ]


def test_accept_keeps_a_session_through_clear(client: TestClient):
    week = _plan(client)
    thursday = next(s for s in week["sessions"] if s["date"] == "2026-11-05")
    _ok(client.post(f"/api/plan/accept/{thursday['id']}", params={"week": W45}))
    week = _ok(client.delete("/api/plan", params={"week": W45}))
    kept = [(d, m) for d, m, e in _meals(week)]
    assert ("2026-11-05", "dinner") in kept
    assert not any(e.get("planned") for _, _, e in _meals(week))
    assert all(d <= "2026-11-08" for d, _ in kept)  # Thursday's cycle only


def test_planning_a_full_week_is_refused(client: TestClient):
    _plan(client)
    response = client.post("/api/plan", params={"week": W45})
    assert response.status_code == 409
    assert "Nothing to add" in response.json()["detail"]


def test_session_rows_tell_planned_from_manual(client: TestClient):
    _ok(_add(client, "2026-11-06", CHICKEN, mealtime="dinner"))  # by hand
    week = _plan(client)
    thursday = next(s for s in week["sessions"] if s["date"] == "2026-11-05")
    chicken = next(i for i in thursday["items"] if i["recipe"] == CHICKEN)
    manual = [m for m in chicken["meals"] if not m["planned"]]
    assert {"date": "2026-11-06", "mealtime": "dinner", "planned": False} in manual
    planned_rows = [i for i in thursday["items"] if i["planned"]]
    assert (
        planned_rows
        and sum(i["planned"] for i in thursday["items"]) == thursday["planned"]
    )


def test_explain_scores_the_week_ahead_whoever_placed_it(client: TestClient):
    # A hand-made lunch missing its veg, then the planner's week.
    _ok(_add(client, "2026-11-06", CHICKEN, mealtime="lunch"))
    _ok(_add(client, "2026-11-06", "boiled-basmati-rice", mealtime="lunch"))
    bill = _ok(client.get("/api/plan/explain"))
    assert bill["start"] == "2026-11-05" and bill["problems"] == []
    (friday,) = [m for m in bill["meals"] if m["date"] == "2026-11-06"]
    assert (friday["mealtime"], friday["archetype"], friday["points"]) == (
        "lunch",
        "plate",
        3,
    )
    assert any(line["reason"] == "plate: veg missing" for line in bill["lines"])

    _plan(client)
    planned = _ok(client.get("/api/plan/explain"))
    assert len(planned["meals"]) > 20  # every meal of the week ahead is read
    assert planned["total"] == sum(t["points"] for t in planned["terms"])
