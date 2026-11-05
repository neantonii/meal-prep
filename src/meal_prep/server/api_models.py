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
    """One logged serving, with the numbers frozen when it was logged.
    ``recipe`` is ``None`` for a free-form entry (takeout, eating out), whose
    unknown numbers are ``None``."""

    id: str
    recipe: str | None
    title: str
    card_url: str | None  # None when the recipe no longer exists
    session: str | None  # id of the prep session it came from
    kcal: float | None
    protein_g: float | None
    carbs_g: float | None
    fat_g: float | None
    fiber_g: float | None
    cost: float | None
    portion: float | None = None  # free-form: share of the order eaten
    estimated: bool = False  # free-form: the numbers are a guess
    assumptions: list[str] = Field(default_factory=list)  # what a guess assumed
    # How a guess was made ("manual" or "ai") and the AI's calories range
    # for the whole order; kept when the entry is edited.
    estimate_source: str | None = None
    kcal_low: float | None = None
    kcal_high: float | None = None


class DiaryMeal(BaseModel):
    mealtime: str
    entries: list[DiaryEntry]


class DiaryDay(BaseModel):
    date: str
    mode: str  # "plan" or "log" (Admin is the client's switch)
    settled: list[str]  # mealtimes whose prep cycle locked (Admin still edits)
    meals: list[DiaryMeal]
    totals: dict[str, float]
    unknown: list[str] = Field(default_factory=list)  # totals missing a number
    estimated: bool = False  # totals include a guess


class MealRef(BaseModel):
    """A diary meal: its day and mealtime."""

    date: str
    mealtime: str


class SessionItem(BaseModel):
    """One recipe of a session: frozen numbers plus made vs eaten."""

    recipe: str
    title: str
    card_url: str | None
    category: str | None  # the recipe's category; None once the recipe is gone
    batches: int
    servings: int
    portions: int  # made: batches x servings
    eaten: int  # linked entries, in every week
    meals: list[MealRef]  # those entries: which days and mealtimes
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


class NeedShare(BaseModel):
    """One recipe's part of a needed ingredient, and whether it is ticked."""

    recipe: str
    title: str
    packages: float | None
    grams: float
    cost: float
    have: bool


class NeededIngredient(BaseModel):
    """One ingredient to have on hand: ``packages`` of ``product`` (a
    fraction is fine); the package fields are ``None`` for lines frozen
    before packages were recorded."""

    ingredient: str
    name: str
    card_url: str | None
    product: str | None
    package_amount: float | None
    package_unit: str | None
    packages: float | None
    grams: float
    cost: float
    recipes: list[str]
    shares: list[NeedShare]  # each recipe's part
    have: bool  # every share ticked for this session
    always: bool  # a staple: on hand in every session


class AisleNeeds(BaseModel):
    """``aisle`` is ``None`` for lines frozen before aisles were recorded."""

    aisle: str | None
    cost: float
    ingredients: list[NeededIngredient]


class HaveShare(BaseModel):
    recipe: str
    ingredient: str


class HaveUpdate(BaseModel):
    """Tick (or untick) recipe shares of ingredients on a session's shopping
    checklist."""

    shares: list[HaveShare]
    have: bool


class AlwaysUpdate(BaseModel):
    """Mark an ingredient as a staple (on hand in every session), or not."""

    always: bool


class SessionDetail(BaseModel):
    """One session for its own page: the card plus totals."""

    session: Session
    today: str
    week: str  # ISO week of the session's date (for the way back)
    totals: dict[str, float]  # portions, cost, kcal, protein_g over all items
    needs: list[AisleNeeds]  # what to have on hand by the session


class DiaryWeek(BaseModel):
    week: str
    today: str
    exists: bool
    days: list[DiaryDay]
    sessions: list[Session]
    totals: dict[str, float]
    unknown: list[str] = Field(default_factory=list)  # totals missing a number
    estimated: bool = False  # totals include a guess


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


class SessionMove(BaseModel):
    date: datetime.date


class FreeFormFields(BaseModel):
    """A free-form entry's title and the numbers of the whole order
    (``None``: unknown); ``portion`` is the share eaten, and the entry keeps
    that share of each number. ``estimated``: the numbers are a guess."""

    title: str = Field(..., min_length=1, max_length=200)
    kcal: float | None = Field(default=None, ge=0)
    protein_g: float | None = Field(default=None, ge=0)
    carbs_g: float | None = Field(default=None, ge=0)
    fat_g: float | None = Field(default=None, ge=0)
    fiber_g: float | None = Field(default=None, ge=0)
    cost: float | None = Field(default=None, ge=0)
    portion: float = Field(default=1.0, gt=0, le=10)
    estimated: bool = False
    # How a guess was made (kept only when ``estimated``): typed in or by AI,
    # with the AI's calories range and assumptions.
    source: Literal["manual", "ai"] = "manual"
    kcal_low: float | None = Field(default=None, ge=0)
    kcal_high: float | None = Field(default=None, ge=0)
    assumptions: list[str] = Field(default_factory=list, max_length=12)


class NewFreeEntries(BaseModel):
    """Free-form entries to add to one slot, in order, from ``position``
    (``None`` appends): a whole takeout order at once."""

    date: datetime.date
    mealtime: Mealtime
    position: int | None = Field(default=None, ge=0)
    items: list[FreeFormFields] = Field(..., min_length=1, max_length=20)


class EstimateRequest(BaseModel):
    """What was eaten, as typed (messy is fine)."""

    text: str = Field(..., min_length=1, max_length=1000)


class EstimatedItemOut(BaseModel):
    """One item of an AI estimate (``meal_prep.server.estimate``)."""

    name: str
    brand: str
    brand_unclear: bool  # no brand given, but the numbers depend on it
    quantity: str
    kcal: float
    kcal_low: float
    kcal_high: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float
    source: str  # "published", "typical" or "guess"
    assumptions: list[str]


class EstimateOut(BaseModel):
    items: list[EstimatedItemOut]


class Usual(BaseModel):
    """A free-form meal eaten before: its latest numbers for the whole order
    (``None``: unknown), when it was last eaten and how often."""

    title: str
    kcal: float | None
    protein_g: float | None
    carbs_g: float | None
    fat_g: float | None
    fiber_g: float | None
    cost: float | None
    estimated: bool
    last: str
    times: int
