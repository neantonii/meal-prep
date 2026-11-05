"""Tests for the prep-session API and the session cards on a week page."""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from meal_prep.server.app import create_app

REPO = Path(__file__).resolve().parents[3]
TODAY = datetime.date(2026, 10, 31)  # Saturday: W44 is mostly Log, W45 Plan
W44, W45, W46 = "2026-W44", "2026-W45", "2026-W46"
CHICKEN = "air-fried-chicken-breast"
RICE = "boiled-basmati-rice"


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    app = create_app(
        REPO / "data", REPO / "recipes", tmp_path / "diary", today=lambda: TODAY
    )
    return TestClient(app)


def _ok(response) -> dict:
    assert response.status_code == 200, response.text
    return response.json()


def _add(client: TestClient, date: str, recipe: str = CHICKEN, **extra) -> dict:
    week = extra.pop("week", W45)
    params = {"admin": "true"} if extra.pop("admin", False) else {}
    body = {"date": date, "mealtime": "lunch", "recipe": recipe, **extra}
    return client.post(f"/api/diary/{week}/entries", json=body, params=params)


def _entries(week: dict) -> list[dict]:
    return [e for d in week["days"] for m in d["meals"] for e in m["entries"]]


def _card(week: dict, date: str) -> dict:
    return next(s for s in week["sessions"] if s["date"] == date)


def test_week_page_shows_default_placeholders_and_modes(client: TestClient):
    week = _ok(client.get(f"/api/diary/{W45}"))
    assert week["today"] == "2026-10-31"
    assert [(s["date"], s["id"]) for s in week["sessions"]] == [
        ("2026-11-01", None),
        ("2026-11-03", None),
        ("2026-11-05", None),
        ("2026-11-08", None),
    ]
    assert {d["mode"] for d in week["days"]} == {"plan"}
    last = _ok(client.get(f"/api/diary/{W44}"))
    assert [d["mode"] for d in last["days"]] == ["log"] * 6 + ["plan"]
    assert _card(last, "2026-10-25")["mode"] == "log"


def test_planning_auto_creates_the_sunday_session_shared_by_two_weeks(
    client: TestClient, tmp_path: Path
):
    week = _ok(_add(client, "2026-11-02"))
    sun = _card(week, "2026-11-01")
    [entry] = _entries(week)
    assert entry["session"] == sun["id"] is not None
    [item] = sun["items"]
    assert (item["recipe"], item["batches"], item["eaten"]) == (CHICKEN, 1, 1)
    assert item["portions"] >= 1
    assert (tmp_path / "diary" / "sessions" / "2026-11-01.yaml").exists()
    # The same session is the last card of the week it falls in.
    last = _ok(client.get(f"/api/diary/{W44}"))
    assert last["sessions"][-1]["id"] == sun["id"]
    assert last["sessions"][-1]["items"][0]["eaten"] == 1


def test_past_drops_auto_link_and_settled_meals_need_admin(client: TestClient):
    week = _ok(_add(client, "2026-11-02"))  # creates Sunday's session
    sun = _card(week, "2026-11-01")["id"]
    # Friday (yesterday, Thursday's cycle) is still open; nothing to link.
    logged = _ok(_add(client, "2026-10-30", week=W44))
    assert _entries(logged)[0]["session"] is None
    # A session later than the entry is refused, Admin or not.
    later = _add(client, "2026-10-30", week=W44, session=sun, admin=True)
    assert later.status_code == 409
    # Mon 26 Oct (Sunday's cycle) locked on Wed 28: Admin only.
    settled = _add(client, "2026-10-26", week=W44)
    assert settled.status_code == 409
    assert "settled" in settled.json()["detail"]
    assert _add(client, "2026-10-26", week=W44, admin=True).status_code == 200


def test_session_items_follow_meals_and_guard_links(client: TestClient):
    # A Wednesday meal auto-links to (and creates) Tuesday's session.
    week = _ok(_add(client, "2026-11-04", RICE))
    tue = _card(week, "2026-11-03")
    [item] = tue["items"]
    assert item["batches"] == 1
    servings = item["servings"]
    sid = tue["id"]
    for _ in range(servings):  # servings + 1 meals: two batches
        week = _ok(_add(client, "2026-11-04", RICE, session=sid))
    assert _card(week, "2026-11-03")["items"][0]["batches"] == 2
    for url in (f"/api/sessions/{sid}/items/{RICE}", f"/api/sessions/{sid}"):
        assert client.delete(url, params={"week": W45}).status_code == 409
    missing = client.delete(
        f"/api/sessions/{sid}/items/{CHICKEN}", params={"week": W45}
    )
    assert missing.status_code == 404
    # Items can't be added without a meal any more.
    added = client.post(
        "/api/sessions/2026-11-05/items", params={"week": W45}, json={"recipe": RICE}
    )
    # No such route: 404, or 405 when a built UI bundle is mounted at "/".
    assert added.status_code in (404, 405)
    assert _card(_ok(client.get(f"/api/diary/{W45}")), "2026-11-05")["id"] is None


def test_moving_a_session_and_pruning_it(client: TestClient, tmp_path: Path):
    week = _ok(_add(client, "2026-11-04", RICE))  # creates Tuesday's session
    sid = _card(week, "2026-11-03")["id"]
    [entry] = _entries(week)
    week = _ok(
        client.patch(
            f"/api/sessions/{sid}", params={"week": W45}, json={"date": "2026-11-02"}
        )
    )
    assert _card(week, "2026-11-02")["id"] == sid
    assert _card(week, "2026-11-03")["id"] is None  # placeholder again
    sessions = tmp_path / "diary" / "sessions"
    assert [p.name for p in sessions.iterdir()] == ["2026-11-02.yaml"]
    assert (
        client.delete(f"/api/sessions/{sid}", params={"week": W45}).status_code == 409
    )
    # Its last meal gone, the Plan session disappears by itself.
    week = _ok(client.delete(f"/api/diary/{W45}/entries/{entry['id']}"))
    assert all(s["id"] is None for s in week["sessions"])
    assert list(sessions.iterdir()) == []


def test_relinking_an_entry_and_older_sessions_show_as_extra_cards(
    client: TestClient,
):
    week = _ok(_add(client, "2026-11-02"))
    sun = _card(week, "2026-11-01")["id"]
    later = _ok(_add(client, "2026-11-10", week=W46, session=None))
    [entry] = _entries(later)
    assert entry["session"] is None
    url = f"/api/diary/{W46}/entries/{entry['id']}/session"
    later = _ok(client.put(url, json={"session": sun}))
    assert _entries(later)[0]["session"] == sun
    assert later["sessions"][0]["id"] == sun
    assert later["sessions"][0]["in_window"] is False
    assert later["sessions"][0]["items"][0]["eaten"] == 2


def test_hand_edits_are_picked_up_and_bad_files_reported(
    client: TestClient, tmp_path: Path
):
    week = _ok(_add(client, "2026-11-02"))
    path = tmp_path / "diary" / "sessions" / "2026-11-01.yaml"
    path.write_text(path.read_text().replace("title: ", "title: Old ", 1))
    week = _ok(client.get(f"/api/diary/{W45}"))
    assert _card(week, "2026-11-01")["items"][0]["title"].startswith("Old ")
    path.write_text("id: nope\n")
    assert client.get(f"/api/diary/{W45}").status_code == 422


def test_dropping_a_meal_on_an_empty_day_creates_its_session(client: TestClient):
    week = _ok(_add(client, "2026-11-06"))  # Friday: auto-links to Thursday
    thu = _card(week, "2026-11-05")["id"]
    [entry] = _entries(week)
    assert entry["session"] == thu is not None
    assert _card(week, "2026-11-03")["id"] is None  # Tuesday: placeholder
    url = f"/api/diary/{W45}/entries/{entry['id']}/session"
    week = _ok(client.put(url, json={"session_date": "2026-11-03"}))
    tue = _card(week, "2026-11-03")
    assert tue["id"] is not None
    assert _entries(week)[0]["session"] == tue["id"]
    assert _card(week, "2026-11-05")["id"] is None  # Thursday: pruned


def test_session_detail_lists_each_items_meals(client: TestClient):
    _ok(_add(client, "2026-11-02"))  # Monday lunch: Sunday's session
    week = _ok(_add(client, "2026-11-01", week=W44, mealtime="dinner"))
    sun = _card(week, "2026-11-01")
    [item] = sun["items"]
    assert item["meals"] == [
        {"date": "2026-11-01", "mealtime": "dinner"},
        {"date": "2026-11-02", "mealtime": "lunch"},
    ]
    detail = _ok(client.get(f"/api/sessions/{sun['id']}"))
    assert detail["week"] == W44
    assert detail["session"]["items"][0]["meals"] == item["meals"]
    assert detail["totals"]["portions"] == item["portions"]
    assert detail["totals"]["cost"] == pytest.approx(item["portions"] * item["cost"])
    missing = client.get("/api/sessions/00000000-0000-4000-8000-000000000000")
    assert missing.status_code == 404


def test_session_detail_lists_what_to_have_by_aisle(client: TestClient):
    week = _ok(_add(client, "2026-11-02"))
    sun = _card(week, "2026-11-01")
    needs = _ok(client.get(f"/api/sessions/{sun['id']}"))["needs"]
    assert needs and all(group["aisle"] for group in needs)
    lines = [line for group in needs for line in group["ingredients"]]
    chicken = next(line for line in lines if line["ingredient"].startswith("boneless"))
    assert chicken["product"] and chicken["package_unit"]
    assert chicken["packages"] > 0
    assert chicken["card_url"].startswith("/cards/ingredient/meat/")
    assert chicken["recipes"] == [sun["items"][0]["title"]]
    assert sum(group["cost"] for group in needs) == pytest.approx(
        sum(line["cost"] for line in lines)
    )


def test_session_items_come_grouped_by_category(client: TestClient):
    # Added carb, breakfast, protein: listed protein, carb, breakfast (the
    # RecipeCategory order the palette uses), each with its category.
    for recipe in (RICE, "flat-white", CHICKEN):
        _ok(_add(client, "2026-11-02", recipe))
    sun = _card(_ok(client.get(f"/api/diary/{W45}")), "2026-11-01")
    assert [(i["recipe"], i["category"]) for i in sun["items"]] == [
        (CHICKEN, "modular_protein"),
        (RICE, "modular_carb"),
        ("flat-white", "breakfast"),
    ]


def _need(detail: dict, ingredient: str) -> dict:
    return next(
        i
        for g in detail["needs"]
        for i in g["ingredients"]
        if i["ingredient"] == ingredient
    )


def _share(detail: dict, ingredient: str, recipe: str) -> dict:
    return next(x for x in _need(detail, ingredient)["shares"] if x["recipe"] == recipe)


def test_shopping_checklist_ticks_recipe_shares_and_staples_across(
    client: TestClient, tmp_path: Path
):
    # Chicken and rice both go into Sunday's session; both use kosher salt.
    _ok(_add(client, "2026-11-02", CHICKEN))
    _ok(_add(client, "2026-11-02", RICE))
    _ok(_add(client, "2026-11-04", RICE))  # Tuesday's session
    week = _ok(client.get(f"/api/diary/{W45}"))
    sun, tue = _card(week, "2026-11-01")["id"], _card(week, "2026-11-03")["id"]
    sun_file = tmp_path / "diary" / "sessions" / "2026-11-01.yaml"
    assert "have:" not in sun_file.read_text()  # only once the checklist is used
    salt = _need(_ok(client.get(f"/api/sessions/{sun}")), "kosher-salt")
    assert {x["recipe"] for x in salt["shares"]} == {CHICKEN, RICE}
    assert salt["grams"] == pytest.approx(sum(x["grams"] for x in salt["shares"]))

    # A recipe's tick covers only its share; the line is had once all are.
    chicken_salt = {"recipe": CHICKEN, "ingredient": "kosher-salt"}
    put = lambda shares, have: client.put(  # noqa: E731
        f"/api/sessions/{sun}/have", json={"shares": shares, "have": have}
    )
    detail = _ok(put([chicken_salt], True))
    assert _share(detail, "kosher-salt", CHICKEN)["have"] is True
    assert _share(detail, "kosher-salt", RICE)["have"] is False
    assert _need(detail, "kosher-salt")["have"] is False
    rice_salt = {"recipe": RICE, "ingredient": "kosher-salt"}
    detail = _ok(put([rice_salt], True))
    assert _need(detail, "kosher-salt")["have"] is True
    assert "kosher-salt" in sun_file.read_text()
    # Unticking is the same call; with nothing ticked the file drops "have".
    detail = _ok(put([chicken_salt, rice_salt], False))
    assert _need(detail, "kosher-salt")["have"] is False
    assert "have:" not in sun_file.read_text()
    # Ticks belong to one session.
    other = _ok(client.get(f"/api/sessions/{tue}"))
    _ok(put([rice_salt], True))
    assert _need(_ok(client.get(f"/api/sessions/{tue}")), "kosher-salt") == _need(
        other, "kosher-salt"
    )

    # A staple spans sessions, and new ingredients start without it.
    detail = _ok(
        client.put(f"/api/sessions/{sun}/always/kosher-salt", json={"always": True})
    )
    assert _need(detail, "kosher-salt")["always"] is True
    other = _ok(client.get(f"/api/sessions/{tue}"))
    assert _need(other, "kosher-salt")["always"] is True
    assert all(
        not i["always"]
        for g in other["needs"]
        for i in g["ingredients"]
        if i["ingredient"] != "kosher-salt"
    )
    assert "kosher-salt" in (tmp_path / "diary" / "staples.yaml").read_text()
    detail = _ok(
        client.put(f"/api/sessions/{sun}/always/kosher-salt", json={"always": False})
    )
    assert _need(detail, "kosher-salt")["always"] is False
    bad = client.put(f"/api/sessions/{sun}/always/no-such-thing", json={"always": True})
    assert bad.status_code == 422
