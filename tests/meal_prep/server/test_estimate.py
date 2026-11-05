"""AI estimates of free-form meals (#141), against a fake service."""

from __future__ import annotations

import datetime
import json
import urllib.error
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from meal_prep.server.app import create_app
from meal_prep.server.estimate import Estimator

REPO = Path(__file__).resolve().parents[3]
TODAY = datetime.date(2026, 11, 5)
WEEK = "2026-W45"
ITEM = {
    "name": "McDonald's Small Fries",
    "brand": "McDonald's",
    "brand_unclear": False,
    "quantity": "1 small order",
    "kcal": 230,
    "kcal_low": 210,
    "kcal_high": 250,
    "protein_g": 3,
    "carbs_g": 30,
    "fat_g": 11,
    "fiber_g": 3,
    "source": "published",
    "assumptions": ["no drink assumed"],
}


class FakeEstimator(Estimator):
    """Answers from ``replies`` (a reply dict, or an exception to raise)
    and records each request body."""

    def __init__(self, *replies: Any) -> None:
        object.__setattr__(self, "replies", list(replies))
        object.__setattr__(self, "sent", [])
        super().__init__(api_key="test")

    def call(self, body: dict[str, Any]) -> dict[str, Any]:
        self.sent.append(body)  # type: ignore[attr-defined]
        reply = self.replies.pop(0)  # type: ignore[attr-defined]
        if isinstance(reply, Exception):
            raise reply
        return reply


def _reply(*items: dict[str, Any]) -> dict[str, Any]:
    content = json.dumps({"items": list(items)})
    return {"choices": [{"message": {"content": content}}]}


def _client(tmp_path: Path, estimator: Estimator | None) -> TestClient:
    app = create_app(
        REPO / "data",
        REPO / "recipes",
        tmp_path / "diary",
        today=lambda: TODAY,
        estimator=estimator,
    )
    return TestClient(app)


def test_estimates_are_off_without_a_key(tmp_path: Path):
    client = _client(tmp_path, None)
    assert client.get("/api/estimate").json() == {"available": False, "model": None}
    response = client.post("/api/estimate", json={"text": "fries"})
    assert response.status_code == 503


def test_an_estimate_splits_the_meal_and_is_cached(tmp_path: Path):
    fake = FakeEstimator(_reply(ITEM, {**ITEM, "name": "McDonald's McChicken"}))
    client = _client(tmp_path, fake)
    assert client.get("/api/estimate").json()["available"]
    text = "mcdonalds meal, mcchicken, small fries"
    first = client.post("/api/estimate", json={"text": text}).json()
    assert [i["name"] for i in first["items"]] == [
        "McDonald's Small Fries",
        "McDonald's McChicken",
    ]
    assert first["items"][0]["assumptions"] == ["no drink assumed"]
    # The same words again (spacing and case aside): no second call.
    again = client.post("/api/estimate", json={"text": f"  {text.upper()} "})
    assert again.json() == first
    [body] = fake.sent  # type: ignore[attr-defined]
    assert body["messages"][-1]["content"] == text
    assert body["response_format"]["type"] == "json_schema"
    assert "Canada" in body["messages"][0]["content"]


@pytest.mark.parametrize(
    "reply",
    [
        {"choices": [{"message": {"content": "not json"}}]},
        _reply({**ITEM, "kcal": -5}),
        {"error": "nope"},
        urllib.error.URLError("down"),
    ],
)
def test_a_failed_estimate_says_so(tmp_path: Path, reply: Any):
    client = _client(tmp_path, FakeEstimator(reply))
    response = client.post("/api/estimate", json={"text": "fries"})
    assert response.status_code == 502
    assert response.json()["detail"]


def test_ai_items_are_saved_together_with_their_assumptions(tmp_path: Path):
    client = _client(tmp_path, None)
    items = [
        {
            "title": "McDonald's Small Fries",
            "kcal": 230,
            "protein_g": 3,
            "estimated": True,
            "source": "ai",
            "kcal_low": 210,
            "kcal_high": 250,
            "assumptions": ["no drink assumed"],
        },
        {"title": "McDonald's McChicken", "kcal": 400, "estimated": True},
    ]
    body = {"date": "2026-11-06", "mealtime": "lunch", "items": items}
    response = client.post(f"/api/diary/{WEEK}/others", json=body)
    assert response.status_code == 200, response.text
    week = response.json()
    entries = [e for d in week["days"] for m in d["meals"] for e in m["entries"]]
    assert [e["title"] for e in entries] == [i["title"] for i in items]
    assert entries[0]["assumptions"] == ["no drink assumed"]
    stored = (tmp_path / "diary" / f"{WEEK}.yaml").read_text()
    assert "source: ai" in stored and "kcal_low: 210" in stored
