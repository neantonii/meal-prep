"""AI estimates of takeout meals (#141), against a fake service."""

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
    "question": "",
    "quantity": "1 small order",
    "kcal": 230,
    "kcal_low": 210,
    "kcal_high": 250,
    "protein_g": 3,
    "carbs_g": 30,
    "fat_g": 11,
    "fiber_g": 3,
    "price": 3.29,
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
    drink = {**ITEM, "name": "Drink", "question": "Which drink? A soda adds 200 kcal"}
    fake = FakeEstimator(_reply(ITEM, {**ITEM, "name": "McDonald's McChicken"}, drink))
    client = _client(tmp_path, fake)
    assert client.get("/api/estimate").json()["available"]
    text = "mcdonalds meal, mcchicken, small fries"
    first = client.post("/api/estimate", json={"text": text}).json()
    assert [i["name"] for i in first["items"]] == [
        "McDonald's Small Fries",
        "McDonald's McChicken",
        "Drink",
    ]
    assert first["items"][2]["question"].startswith("Which drink?")
    assert first["items"][0]["assumptions"] == ["no drink assumed"]
    assert first["items"][0]["price"] == 3.29
    # The same words again (spacing and case aside): no second call.
    again = client.post("/api/estimate", json={"text": f"  {text.upper()} "})
    assert again.json() == first
    [body] = fake.sent  # type: ignore[attr-defined]
    assert body["messages"][-1]["content"] == text
    assert body["response_format"]["type"] == "json_schema"
    assert "Canada" in body["messages"][0]["content"]
    assert "Canadian dollars" in body["messages"][0]["content"]


@pytest.mark.parametrize(
    "reply",
    [
        {"choices": [{"message": {"content": "not json"}}]},
        _reply({**ITEM, "kcal": -5}),
        {"error": "nope"},
        urllib.error.URLError("down"),
        json.JSONDecodeError("Expecting value", "<html>error</html>", 0),
    ],
)
def test_a_failed_estimate_says_so(tmp_path: Path, reply: Any):
    client = _client(tmp_path, FakeEstimator(reply))
    response = client.post("/api/estimate", json={"text": "fries"})
    assert response.status_code == 502
    assert response.json()["detail"]


PHOTO = "data:image/jpeg;base64," + "A" * 64


def test_photos_go_to_the_model_with_the_text(tmp_path: Path):
    fake = FakeEstimator(_reply(ITEM), _reply(ITEM))
    client = _client(tmp_path, fake)
    response = client.post("/api/estimate", json={"images": [PHOTO]})
    assert response.status_code == 200, response.text
    [body] = fake.sent  # type: ignore[attr-defined]
    content = body["messages"][-1]["content"]
    assert content[0]["type"] == "text"  # a default prompt for a photo alone
    assert content[1] == {"type": "image_url", "image_url": {"url": PHOTO}}
    # The same text with a different photo is a different estimate.
    other = PHOTO.replace("AAAA", "BBBB", 1)
    client.post("/api/estimate", json={"images": [other]})
    assert len(fake.sent) == 2  # type: ignore[attr-defined]


def test_heic_photos_are_accepted_as_sent(tmp_path: Path):
    # Browsers that can't read HEIC (desktop Chrome, Firefox) send it as is.
    fake = FakeEstimator(_reply(ITEM))
    heic = "data:image/heic;base64," + "A" * 64
    response = _client(tmp_path, fake).post("/api/estimate", json={"images": [heic]})
    assert response.status_code == 200, response.text
    [body] = fake.sent  # type: ignore[attr-defined]
    assert body["messages"][-1]["content"][1]["image_url"]["url"] == heic


@pytest.mark.parametrize(
    "body",
    [
        {"text": "  "},  # nothing to estimate
        {"images": ["https://example.com/pho.jpg"]},  # not a data URL
        {"images": ["data:image/gif;base64,AAAA"]},  # not JPEG, PNG, WebP or HEIC
        {"images": [PHOTO] * 4},  # more than 3
    ],
)
def test_bad_estimate_requests_are_refused(tmp_path: Path, body: dict):
    client = _client(tmp_path, FakeEstimator())
    assert client.post("/api/estimate", json=body).status_code == 422
