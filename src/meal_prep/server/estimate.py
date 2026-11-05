"""AI estimates for free-form diary entries (#141): a messy description of
what was eaten -> separate items with clean names, brand, numbers, a
calories range, the assumptions behind them, and a question where something
unsaid changes the numbers.

Calls an OpenAI-compatible chat completions API (Gemini's by default) with a
JSON schema for the reply, using only the standard library. Configured by
the host's environment:

- ``MEAL_PREP_ESTIMATE_KEY`` (or ``GEMINI_API_KEY``): the API key. Without
  one, estimates are off and the UI hides the button.
- ``MEAL_PREP_ESTIMATE_MODEL``: default ``gemini-3.5-flash-lite``.
- ``MEAL_PREP_ESTIMATE_URL``: the chat completions endpoint; default
  Gemini's OpenAI-compatible one.
- ``MEAL_PREP_ESTIMATE_COUNTRY``: whose menus to assume; default Canada.

Replies are cached by normalized description, so asking twice costs one
call.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger("meal_prep.server")

DEFAULT_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
DEFAULT_MODEL = "gemini-3.5-flash-lite"
_CACHE_SIZE = 200
_TIMEOUT_S = 30


class EstimateError(RuntimeError):
    """The estimate could not be made; the message is user-facing."""


class EstimatedItem(BaseModel):
    """One item of a meal, as the model estimates it."""

    name: str = Field(..., min_length=1, max_length=120)
    brand: str = Field(default="", max_length=60)
    question: str = Field(default="", max_length=200)
    quantity: str = Field(default="", max_length=60)
    kcal: float = Field(..., ge=0, le=10000)
    kcal_low: float = Field(..., ge=0, le=10000)
    kcal_high: float = Field(..., ge=0, le=10000)
    protein_g: float = Field(..., ge=0, le=1000)
    carbs_g: float = Field(..., ge=0, le=1000)
    fat_g: float = Field(..., ge=0, le=1000)
    fiber_g: float = Field(default=0, ge=0, le=1000)
    source: Literal["published", "typical", "guess"]
    assumptions: list[str] = Field(default_factory=list, max_length=8)


class EstimateReply(BaseModel):
    items: list[EstimatedItem] = Field(..., min_length=1, max_length=20)


_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "brand": {"type": "string"},
                    "question": {"type": "string"},
                    "quantity": {"type": "string"},
                    "kcal": {"type": "number"},
                    "kcal_low": {"type": "number"},
                    "kcal_high": {"type": "number"},
                    "protein_g": {"type": "number"},
                    "carbs_g": {"type": "number"},
                    "fat_g": {"type": "number"},
                    "fiber_g": {"type": "number"},
                    "source": {
                        "type": "string",
                        "enum": ["published", "typical", "guess"],
                    },
                    "assumptions": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "name",
                    "brand",
                    "question",
                    "quantity",
                    "kcal",
                    "kcal_low",
                    "kcal_high",
                    "protein_g",
                    "carbs_g",
                    "fat_g",
                    "fiber_g",
                    "source",
                    "assumptions",
                ],
            },
        }
    },
    "required": ["items"],
}


def _prompt(country: str) -> str:
    return f"""You estimate the nutrition of meals someone ate, for a food diary.
The user describes what they ate, often messily: misspelled, several items in
one line, details left out. Split it into menu items, the separate things
one would order or be served, and estimate each one.
Everything was eaten as served (takeout, restaurant, someone else's
cooking): a weight is always the weight of the food as served.

List every part of the meal, including parts the description only implies
(a combo or "meal" implies a drink; "burger and fries" may imply a sauce), so
the user sees each part and can fix or delete it. Never fold a part into
another item or leave it out silently.

For every item:
- name: the item as a menu would list it: the brand when known, then the
  size or count whenever it changes the numbers (a different size is a
  different menu item), then the dish, e.g. "McDonald's McChicken",
  "McDonald's Small Fries", "McDonald's 6 Chicken McNuggets", "Large Pho with
  Brisket", "Drink".
  Use what the user said: their count and size, and no ingredients or
  variants they didn't mention. If something they said looks wrong (a size
  the menu doesn't have), keep it in the name and estimate it, and ask in
  the question.
  A brand or restaurant mentioned once applies to the whole order unless the
  user says otherwise.
- brand: the restaurant or product brand, or "" when there is none.
- quantity: the amount the numbers are for, e.g. "1 sandwich", "6 pieces",
  "250 g", "1 cup", "355 ml".
- kcal and macros (grams) for that quantity, with kcal_low/kcal_high a
  realistic range. Use the brand's published values for {country} menus when
  you know them (source "published"), otherwise typical values ("typical"),
  or "guess" when the item itself is vague.
- question: when something the user didn't say changes the numbers a lot
  (which drink, which brand, the size, a sauce), ask it
  in one short question that says what is at stake, e.g. "Which drink? A
  regular soda adds about 200 kcal." Still give your best estimate. "" when
  nothing important is unclear.
- assumptions: short notes on assumptions that change the numbers (no oil
  added, regular not diet). Never restate the name, size or quantity. Usually
  empty."""


@dataclass(frozen=True, slots=True)
class Estimator:
    """Estimates meals through one chat completions endpoint."""

    api_key: str
    model: str = DEFAULT_MODEL
    url: str = DEFAULT_URL
    country: str = "Canada"

    @classmethod
    def from_env(cls) -> Estimator | None:
        """The configured estimator, or ``None`` when no key is set."""
        key = os.environ.get("MEAL_PREP_ESTIMATE_KEY") or os.environ.get(
            "GEMINI_API_KEY"
        )
        if not key:
            return None
        return cls(
            api_key=key,
            model=os.environ.get("MEAL_PREP_ESTIMATE_MODEL", DEFAULT_MODEL),
            url=os.environ.get("MEAL_PREP_ESTIMATE_URL", DEFAULT_URL),
            country=os.environ.get("MEAL_PREP_ESTIMATE_COUNTRY", "Canada"),
        )

    def request(self, text: str) -> dict[str, Any]:
        """The chat completions request body for ``text``."""
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _prompt(self.country)},
                {"role": "user", "content": text},
            ],
            "temperature": 0.2,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "meal_estimate", "schema": _SCHEMA},
            },
        }

    def call(self, body: dict[str, Any]) -> dict[str, Any]:
        """POST ``body``; the decoded JSON reply. Tests replace this."""
        request = urllib.request.Request(
            self.url,
            data=json.dumps(body).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=_TIMEOUT_S) as response:
            reply: dict[str, Any] = json.load(response)
            return reply

    def estimate(self, text: str) -> EstimateReply:
        """Split and estimate ``text``; ``EstimateError`` with a user-facing
        message when the service or its reply fails."""
        try:
            reply = self.call(self.request(text))
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            logger.warning("estimate failed: HTTP %s %s", e.code, detail)
            raise EstimateError(
                f"The estimate service refused the request (HTTP {e.code})"
            ) from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            logger.warning("estimate failed: %s", e)
            raise EstimateError("Couldn't reach the estimate service") from e
        try:
            content = reply["choices"][0]["message"]["content"]
            return EstimateReply.model_validate_json(content)
        except (KeyError, IndexError, TypeError, ValidationError) as e:
            logger.warning("estimate reply unusable: %s", str(reply)[:500])
            raise EstimateError(
                "The estimate came back malformed: enter the numbers by hand"
            ) from e


def cache_key(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


class CachedEstimator:
    """Remembers the latest replies by normalized description (in memory)."""

    def __init__(self, estimator: Estimator, size: int = _CACHE_SIZE) -> None:
        self.estimator = estimator
        self.size = size
        self._cache: OrderedDict[str, EstimateReply] = OrderedDict()

    def estimate(self, text: str) -> EstimateReply:
        key = cache_key(text)
        hit = self._cache.get(key)
        if hit is not None:
            self._cache.move_to_end(key)
            return hit
        reply = self.estimator.estimate(text)
        self._cache[key] = reply
        while len(self._cache) > self.size:
            self._cache.popitem(last=False)
        return reply
