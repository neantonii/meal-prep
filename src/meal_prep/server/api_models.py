"""Request and response shapes of the diary server's JSON API (``ui/src/api.ts``
mirrors them)."""

from __future__ import annotations

import datetime
import re
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

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


class _EntryOut(BaseModel):
    """What every logged serving shows: calories and macros, as logged."""

    id: str
    title: str
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float


class RecipeEntryOut(_EntryOut):
    """A serving of a catalog recipe."""

    kind: Literal["recipe"] = "recipe"
    recipe: str
    card_url: str | None  # None when the recipe no longer exists
    session: str | None  # id of the prep session it came from
    # Eaten later than the dish keeps in the fridge, so frozen in between;
    # False when the session doesn't record its fridge life (older files).
    frozen: bool
    freezer_friendly: bool | None  # None: not recorded
    fiber_g: float
    cost: float


class TakeoutEntryOut(_EntryOut):
    """A takeout meal: never from a session; its cost only if known."""

    kind: Literal["takeout"] = "takeout"
    cost: float | None


# One logged serving, told apart by ``kind``.
type DiaryEntry = Annotated[
    RecipeEntryOut | TakeoutEntryOut, Field(discriminator="kind")
]


class DiaryMeal(BaseModel):
    mealtime: str
    entries: list[DiaryEntry]


class DiaryDay(BaseModel):
    date: str
    mode: str  # "plan" or "log" (Admin is the client's switch)
    settled: list[str]  # mealtimes whose prep cycle locked (Admin still edits)
    meals: list[DiaryMeal]
    totals: dict[str, float]


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
    category_label: str | None  # its display name (``category_display_name``)
    batches: int
    servings: int
    portions: int  # made: batches x servings
    eaten: int  # its meals on days, in every week
    meals: list[MealRef]  # those meals: which days and mealtimes
    unassigned: int  # its meals with no day yet
    binned: int  # its meals thrown away
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


class UnassignedSource(BaseModel):
    """Unassigned portions of one recipe from one session."""

    session: str
    date: str  # the session's date: no day before it can take them
    count: int


class UnassignedRecipe(BaseModel):
    """The unassigned portions of one recipe, over every session."""

    recipe: str
    title: str
    card_url: str | None
    count: int
    kcal: float
    protein_g: float
    freezer_friendly: bool | None  # None: not recorded
    sources: list[UnassignedSource]  # latest session first
    meals: list[str]  # the portions' ids, oldest session first


class BinnedMeal(BaseModel):
    """A portion thrown away."""

    id: str
    recipe: str
    title: str
    cost: float
    binned: str  # the day it went to the bin
    session: str
    session_date: str | None  # None when the session is gone


class Bin(BaseModel):
    """Everything thrown away so far; ``meals`` latest first."""

    count: int
    cost: float
    meals: list[BinnedMeal]


class DiaryWeek(BaseModel):
    week: str
    today: str
    exists: bool
    days: list[DiaryDay]
    sessions: list[Session]
    unassigned: list[UnassignedRecipe]
    bin: Bin
    totals: dict[str, float]


class NewEntry(BaseModel):
    """A recipe to cook one more batch of, with one portion on this day
    (the rest go to unassigned); ``position`` is its index in the slot,
    ``None`` appends. ``session``: the session that cooks it; ``None`` is
    the session of the meal's prep cycle."""

    date: datetime.date
    mealtime: Mealtime
    recipe: str
    position: int | None = Field(default=None, ge=0)
    session: uuid.UUID | None = None


class UnassignedTake(BaseModel):
    """An unassigned portion of ``recipe`` to put on a day."""

    date: datetime.date
    mealtime: Mealtime
    recipe: str
    position: int | None = Field(default=None, ge=0)


class SlotMove(BaseModel):
    """Move a meal to one of the slots without a date."""

    slot: Literal["unassigned", "bin"]


class EntryPlacement(BaseModel):
    """Where to put an entry; ``position`` is its index in the destination
    slot (after it leaves its old place), ``None`` appends."""

    date: datetime.date
    mealtime: Mealtime
    position: int | None = Field(default=None, ge=0)


class ItemMove(BaseModel):
    """Where a recipe line goes: a session id, or ``date``: the session on
    that day, created when the day has none yet."""

    session: uuid.UUID | None = None
    date: datetime.date | None = None

    @model_validator(mode="after")
    def validate_one(self) -> ItemMove:
        if (self.session is None) == (self.date is None):
            raise ValueError("Give either the session or the day")
        return self


class SessionMove(BaseModel):
    date: datetime.date


class TakeoutFields(BaseModel):
    """A takeout meal as typed (one portion): its title, calories and
    macros, and its cost when known."""

    title: str = Field(..., min_length=1, max_length=200)
    kcal: float = Field(..., ge=0)
    protein_g: float = Field(..., ge=0)
    carbs_g: float = Field(..., ge=0)
    fat_g: float = Field(..., ge=0)
    cost: float | None = Field(default=None, ge=0)


class NewTakeoutEntries(BaseModel):
    """Takeout meals to add to one slot, in order, from ``position``
    (``None`` appends): a whole order at once."""

    date: datetime.date
    mealtime: Mealtime
    position: int | None = Field(default=None, ge=0)
    items: list[TakeoutFields] = Field(..., min_length=1, max_length=20)


# A photo as the browser sends it: normally a JPEG it has shrunk to a few
# hundred KB; a HEIC/HEIF the browser can't read (desktop Chrome, Firefox) is
# sent as is, so the limit leaves room for a full-size iPhone photo.
_PHOTO = re.compile(r"data:image/(jpeg|png|webp|heic|heif);base64,[A-Za-z0-9+/=]+")
_PHOTO_MAX = 16_000_000  # characters of base64, about 12 MB


class EstimateRequest(BaseModel):
    """What was eaten, as typed (messy is fine), and/or up to 3 photos of
    the meal, a menu or a receipt."""

    text: str = Field(default="", max_length=1000)
    images: list[str] = Field(default_factory=list, max_length=3)

    @field_validator("images")
    @classmethod
    def validate_images(cls, images: list[str]) -> list[str]:
        for url in images:
            if len(url) > _PHOTO_MAX or not _PHOTO.fullmatch(url):
                raise ValueError(
                    "Each photo must be a JPEG, PNG, WebP or HEIC under 12 MB"
                )
        return images

    @model_validator(mode="after")
    def validate_something(self) -> EstimateRequest:
        if not self.text.strip() and not self.images:
            raise ValueError("Describe the meal or add a photo")
        return self


class EstimatedItemOut(BaseModel):
    """One item of an AI estimate (``meal_prep.server.estimate``)."""

    name: str
    brand: str
    question: str  # what is unclear and changes the numbers ("" when nothing)
    quantity: str
    kcal: float
    kcal_low: float
    kcal_high: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float
    price: float  # rough typical price in CAD
    source: str  # "published", "typical" or "guess"
    assumptions: list[str]


class EstimateOut(BaseModel):
    items: list[EstimatedItemOut]


class Usual(TakeoutFields):
    """A takeout meal eaten before: its latest numbers, when it was last
    eaten and how often."""

    last: str
    times: int
