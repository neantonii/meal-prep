"""Request and response shapes of the diary server's JSON API (``ui/src/api.ts``
mirrors them)."""

from __future__ import annotations

import datetime
import uuid
from typing import Literal

from pydantic import BaseModel, Field

from meal_prep.enums import Mealtime


class CatalogEntry(BaseModel):
    id: str
    title: str
    category: str
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    cost: float


class DiaryEntry(BaseModel):
    """One logged serving, with the numbers frozen when it was logged."""

    id: str
    recipe: str
    title: str
    card_url: str | None  # None when the recipe no longer exists
    session: str | None  # id of the prep session it came from
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float
    cost: float


class DiaryMeal(BaseModel):
    mealtime: str
    entries: list[DiaryEntry]


class DiaryDay(BaseModel):
    date: str
    mode: str  # "plan" or "log" (Admin is the client's switch)
    meals: list[DiaryMeal]
    totals: dict[str, float]


class SessionItem(BaseModel):
    """One recipe of a session: frozen numbers plus made vs eaten."""

    recipe: str
    title: str
    card_url: str | None
    batches: int
    servings: int
    portions: int  # made: batches x servings
    eaten: int  # linked entries, in every week
    kcal: float
    protein_g: float
    cost: float


class Session(BaseModel):
    """A session card; ``id`` is ``None`` for an empty default placeholder."""

    id: str | None
    date: str
    mode: str  # "plan" or "log"
    in_window: bool  # False: an older session linked from this week
    items: list[SessionItem]


class DiaryWeek(BaseModel):
    week: str
    today: str
    exists: bool
    days: list[DiaryDay]
    sessions: list[Session]
    totals: dict[str, float]


class NewEntry(BaseModel):
    """A recipe to log; ``position`` is its index in the slot, ``None``
    appends. ``session``: a session id, ``None`` (unlinked) or ``"auto"``
    (a palette drop: auto-linked in Plan)."""

    date: datetime.date
    mealtime: Mealtime
    recipe: str
    position: int | None = Field(default=None, ge=0)
    session: uuid.UUID | Literal["auto"] | None = "auto"


class EntryPlacement(BaseModel):
    """Where to put an entry; ``position`` is its index in the destination
    slot (after it leaves its old place), ``None`` appends."""

    date: datetime.date
    mealtime: Mealtime
    position: int | None = Field(default=None, ge=0)


class EntryLink(BaseModel):
    """A session id (``None`` unlinks), or ``session_date``: the session on
    that day, created when the day has none yet."""

    session: uuid.UUID | None = None
    session_date: datetime.date | None = None


class ItemUpdate(BaseModel):
    batches: int = Field(..., ge=1)


class SessionMove(BaseModel):
    date: datetime.date
