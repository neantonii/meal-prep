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


def test_planning_creates_the_sunday_session_shared_by_two_weeks(
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


def _take(client: TestClient, date: str, recipe: str = CHICKEN, week: str = W45):
    body = {"date": date, "mealtime": "lunch", "recipe": recipe}
    return client.post(f"/api/diary/{week}/unassigned", json=body)


def test_a_batch_puts_its_other_portions_in_unassigned(client: TestClient):
    week = _ok(_add(client, "2026-11-02"))
    [item] = _card(week, "2026-11-01")["items"]
    servings = item["servings"]
    assert (item["eaten"], item["unassigned"], item["binned"]) == (1, servings - 1, 0)
    [row] = week["unassigned"]
    assert (row["recipe"], row["count"]) == (CHICKEN, servings - 1)
    assert row["sources"] == [
        {
            "session": _card(week, "2026-11-01")["id"],
            "date": "2026-11-01",
            "count": servings - 1,
        }
    ]
    assert _ok(client.get(f"/api/diary/{W46}"))["unassigned"] == week["unassigned"]
    # Before the session's day there is nothing to take.
    early = _take(client, "2026-10-31", week=W44)
    assert early.status_code == 409 and "can't be eaten" in early.json()["detail"]
    # Taking one cooks nothing.
    week = _ok(_take(client, "2026-11-03"))
    [item] = _card(week, "2026-11-01")["items"]
    assert (item["batches"], item["eaten"], item["unassigned"]) == (1, 2, servings - 2)
    assert _take(client, "2026-11-03", RICE).status_code == 409


def test_cooked_sessions_take_no_batch_and_settled_meals_need_admin(
    client: TestClient,
):
    week = _ok(_add(client, "2026-11-02"))  # creates Sunday's session
    sun = _card(week, "2026-11-01")["id"]
    # Friday (yesterday) is in Thursday's cycle, which is cooked: refused.
    logged = _add(client, "2026-10-30", week=W44)
    assert logged.status_code == 409
    assert "already cooked" in logged.json()["detail"]
    # A session later than the meal is refused, Admin or not.
    later = _add(client, "2026-10-30", week=W44, session=sun, admin=True)
    assert later.status_code == 409
    # Admin records it after the fact: Thursday's session gets the batch.
    logged = _ok(_add(client, "2026-10-30", week=W44, admin=True))
    assert _card(logged, "2026-10-29")["items"][0]["recipe"] == CHICKEN
    # Mon 26 Oct (Sunday's cycle) locked on Wed 28: Admin only.
    settled = _take(client, "2026-10-26", week=W44)
    assert settled.status_code == 409
    assert "settled" in settled.json()["detail"]


def test_batches_are_removed_one_at_a_time_from_unassigned(client: TestClient):
    week = _ok(_add(client, "2026-11-04"))  # creates Tuesday's session
    tue = _card(week, "2026-11-03")
    sid, servings = tue["id"], tue["items"][0]["servings"]
    assert servings >= 2
    week = _ok(_add(client, "2026-11-04", session=sid))  # a second batch
    [item] = _card(week, "2026-11-03")["items"]
    assert (item["batches"], item["unassigned"]) == (2, 2 * servings - 2)
    url = f"/api/sessions/{sid}/items/{CHICKEN}/batch"
    week = _ok(client.delete(url, params={"week": W45}))
    [item] = _card(week, "2026-11-03")["items"]
    assert (item["batches"], item["eaten"]) == (1, 2)
    assert item["unassigned"] == servings - 2
    # The last batch goes only once nothing is on a day.
    refused = client.delete(url, params={"week": W45})
    assert refused.status_code == 409
    assert "to unassigned first" in refused.json()["detail"]
    for entry in _entries(week):
        week = _ok(client.delete(f"/api/diary/{W45}/entries/{entry['id']}"))
    week = _ok(client.delete(url, params={"week": W45}))
    assert _card(week, "2026-11-03")["id"] is None  # placeholder again
    assert week["unassigned"] == []
    missing = client.delete(
        f"/api/sessions/{sid}/items/{RICE}/batch", params={"week": W45}
    )
    assert missing.status_code == 404
    # Recipe lines and sessions are no longer deleted directly.
    for gone in (f"/api/sessions/{sid}/items/{CHICKEN}", f"/api/sessions/{sid}"):
        # No such route: 404, or 405 when a built UI bundle is mounted at "/".
        assert client.delete(gone, params={"week": W45}).status_code in (404, 405)


def test_moving_a_session(client: TestClient, tmp_path: Path):
    week = _ok(_add(client, "2026-11-04", RICE))  # creates Tuesday's session
    sid = _card(week, "2026-11-03")["id"]
    week = _ok(
        client.patch(
            f"/api/sessions/{sid}", params={"week": W45}, json={"date": "2026-11-02"}
        )
    )
    assert _card(week, "2026-11-02")["id"] == sid
    assert _card(week, "2026-11-03")["id"] is None  # placeholder again
    sessions = tmp_path / "diary" / "sessions"
    assert [p.name for p in sessions.iterdir()] == ["2026-11-02.yaml"]


def test_the_bin_and_back(client: TestClient, tmp_path: Path):
    week = _ok(_add(client, "2026-11-02"))
    [entry] = _entries(week)
    servings = _card(week, "2026-11-01")["items"][0]["servings"]
    url = f"/api/diary/{W45}/entries/{entry['id']}"
    week = _ok(client.put(f"{url}/slot", json={"slot": "bin"}))
    assert _entries(week) == []
    [binned] = week["bin"]["meals"]
    assert (binned["id"], binned["binned"]) == (entry["id"], "2026-10-31")
    assert binned["session_date"] == "2026-11-01"
    assert week["bin"]["count"] == 1
    assert week["bin"]["cost"] == pytest.approx(entry["cost"])
    [item] = _card(week, "2026-11-01")["items"]
    assert (item["eaten"], item["unassigned"], item["binned"]) == (0, servings - 1, 1)
    assert "binned: '2026-10-31'" in (tmp_path / "diary" / "bin.yaml").read_text()
    # Out of the bin: onto a day, or back with the unassigned ones.
    week = _ok(client.patch(url, json={"date": "2026-11-03", "mealtime": "lunch"}))
    assert [e["id"] for e in _entries(week)] == [entry["id"]]
    assert week["bin"] == {"count": 0, "cost": 0, "meals": []}
    week = _ok(client.put(f"{url}/slot", json={"slot": "unassigned"}))
    assert week["unassigned"][0]["count"] == servings
    assert client.put(f"{url}/slot", json={"slot": "freezer"}).status_code == 422


def test_a_recipe_line_moves_to_another_session(client: TestClient):
    week = _ok(_add(client, "2026-11-06"))  # Friday: Thursday's session
    thu = _card(week, "2026-11-05")
    [entry] = _entries(week)
    assert entry["session"] == thu["id"] is not None
    assert _card(week, "2026-11-03")["id"] is None  # Tuesday: placeholder
    url = f"/api/sessions/{thu['id']}/items/{CHICKEN}/session"
    week = _ok(client.put(url, params={"week": W45}, json={"date": "2026-11-03"}))
    tue = _card(week, "2026-11-03")
    assert tue["id"] is not None
    assert tue["items"][0]["unassigned"] == thu["items"][0]["unassigned"]
    assert _entries(week)[0]["session"] == tue["id"]
    assert week["unassigned"][0]["sources"][0]["date"] == "2026-11-03"
    assert _card(week, "2026-11-05")["id"] is None  # Thursday: nothing left
    # Past its own meal is refused; so is a request naming no target.
    url = f"/api/sessions/{tue['id']}/items/{CHICKEN}/session"
    late = client.put(url, params={"week": W45}, json={"date": "2026-11-08"})
    assert late.status_code == 409 and "move that meal first" in late.json()["detail"]
    assert client.put(url, params={"week": W45}, json={}).status_code == 422


def test_meals_eaten_past_the_fridge_life_show_as_frozen(client: TestClient):
    week = _ok(_add(client, "2026-11-02"))
    [entry] = _entries(week)
    assert entry["frozen"] is False
    assert entry["freezer_friendly"] is not None
    # Two weeks later is past any fridge life: frozen in between.
    later = _ok(_take(client, "2026-11-16", week="2026-W47"))
    [thawed] = _entries(later)
    assert thawed["frozen"] is True
    # Its session shows on that page as an older card, with its date.
    assert later["sessions"][0]["in_window"] is False
    assert later["sessions"][0]["date"] == "2026-11-01"


def test_older_files_load_and_show_a_spare_portion(client: TestClient, tmp_path: Path):
    week = _ok(_add(client, "2026-11-02"))
    servings = _card(week, "2026-11-01")["items"][0]["servings"]
    # As before portions were meals: no slot file, no fridge life recorded.
    (tmp_path / "diary" / "unassigned.yaml").unlink()
    path = tmp_path / "diary" / "sessions" / "2026-11-01.yaml"
    kept = [
        line
        for line in path.read_text().splitlines()
        if "fridge_days" not in line and "freezer_friendly" not in line
    ]
    path.write_text("\n".join(kept) + "\n")
    week = _ok(client.get(f"/api/diary/{W45}"))
    [item] = _card(week, "2026-11-01")["items"]
    assert (item["portions"], item["eaten"], item["unassigned"]) == (servings, 1, 0)
    assert week["unassigned"] == []
    [entry] = _entries(week)
    assert (entry["frozen"], entry["freezer_friendly"]) == (False, None)


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


def test_session_detail_lists_each_items_meals(client: TestClient):
    _ok(_add(client, "2026-11-02"))  # Monday lunch: Sunday's session
    week = _ok(_add(client, "2026-11-01", week=W44, mealtime="dinner"))
    sun = _card(week, "2026-11-01")
    [item] = sun["items"]
    assert item["meals"] == [
        {"date": "2026-11-01", "mealtime": "dinner", "planned": False},
        {"date": "2026-11-02", "mealtime": "lunch", "planned": False},
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
    # RecipeCategory order the palette uses), each with its category and
    # the category's display name.
    for recipe in (RICE, "flat-white", CHICKEN):
        _ok(_add(client, "2026-11-02", recipe))
    sun = _card(_ok(client.get(f"/api/diary/{W45}")), "2026-11-01")
    assert [
        (i["recipe"], i["category"], i["category_label"]) for i in sun["items"]
    ] == [
        (CHICKEN, "modular_protein", "Protein"),
        (RICE, "modular_carb", "Carbs"),
        ("flat-white", "breakfast", "Breakfast"),
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


def test_slot_files_are_validated_like_the_rest_of_the_diary(
    client: TestClient, tmp_path: Path
):
    _ok(_add(client, "2026-11-02"))
    path = tmp_path / "diary" / "unassigned.yaml"
    text = path.read_text()
    assert "session:" in text and "binned" not in text
    # A portion must name its session.
    path.write_text(
        "\n".join(line for line in text.splitlines() if "session:" not in line)
    )
    broken = client.get(f"/api/diary/{W45}")
    assert broken.status_code == 422
    assert "has no prep session" in broken.json()["detail"]
    # An empty or missing file is an empty slot.
    path.write_text("")
    assert _ok(client.get(f"/api/diary/{W45}"))["unassigned"] == []
    path.unlink()
    assert _ok(client.get(f"/api/diary/{W45}"))["unassigned"] == []
