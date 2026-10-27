"""FastAPI diary server: catalog + diary entry API over flat YAML files.

The diary is edited one entry at a time (add, remove, move/reorder). An
entry's numbers are frozen when it is added and never recomputed (#107).
"""

from __future__ import annotations

import datetime
import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from meal_prep import renderer
from meal_prep.adapters.logs import (
    delete_diary_week,
    load_diary_week,
    save_diary_week,
)
from meal_prep.dtos.log import DiaryWeekDTO
from meal_prep.enums import Mealtime, RecipeCategory
from meal_prep.ingredient_cards import render_ingredient_card
from meal_prep.library import load_library
from meal_prep.models.ingredient import MacrosInfo
from meal_prep.models.library import Library
from meal_prep.models.log import LogEntry
from meal_prep.server.weeks import current_week, week_dates
from meal_prep.services.diary import (
    EntryNotFoundError,
    add_entry,
    move_entry,
    remove_entry,
)
from meal_prep.services.logs import prepare_diary_week

logger = logging.getLogger("meal_prep.server")


class _State:
    library: Library
    diary_dir: Path


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
    meals: list[DiaryMeal]
    totals: dict[str, float]


class DiaryWeek(BaseModel):
    week: str
    exists: bool
    days: list[DiaryDay]
    totals: dict[str, float]


class NewEntry(BaseModel):
    """A recipe to log; ``position`` is its index in the slot, ``None``
    appends."""

    date: datetime.date
    mealtime: Mealtime
    recipe: str
    position: int | None = Field(default=None, ge=0)


class EntryPlacement(BaseModel):
    """Where to put an entry; ``position`` is its index in the destination
    slot (after it leaves its old place), ``None`` appends."""

    date: datetime.date
    mealtime: Mealtime
    position: int | None = Field(default=None, ge=0)


def _totals(cost: float, macros: MacrosInfo) -> dict[str, float]:
    return {
        "kcal": macros.calories_kcal,
        "protein_g": macros.protein_g,
        "carbs_g": macros.carbs_g,
        "fat_g": macros.fat_g,
        "fiber_g": macros.fiber_g,
        "cost": cost,
    }


def _entry_out(entry: LogEntry, library: Library) -> DiaryEntry:
    recipe = library.recipes.get(entry.recipe_id)
    return DiaryEntry(
        id=entry.entry_id,
        recipe=entry.recipe_id,
        title=entry.title,
        card_url=(
            f"/cards/recipe/{recipe.category.value}/{recipe.id}.html"
            if recipe is not None
            else None
        ),
        kcal=entry.macros.calories_kcal,
        protein_g=entry.macros.protein_g,
        carbs_g=entry.macros.carbs_g,
        fat_g=entry.macros.fat_g,
        fiber_g=entry.macros.fiber_g,
        cost=entry.cost,
    )


def _week_response(week: str, dto: DiaryWeekDTO | None, library: Library) -> DiaryWeek:
    """The full week for the UI: all 7 days, totals from frozen numbers."""
    logged = prepare_diary_week(dto) if dto is not None else None
    by_date = {d.date: d for d in logged.days} if logged is not None else {}
    days = []
    for date in week_dates(week):
        day = by_date.get(date)
        if day is None:
            days.append(
                DiaryDay(
                    date=date.isoformat(),
                    meals=[],
                    totals=_totals(0.0, MacrosInfo.zero()),
                )
            )
            continue
        days.append(
            DiaryDay(
                date=date.isoformat(),
                meals=[
                    DiaryMeal(
                        mealtime=meal.mealtime.value,
                        entries=[_entry_out(e, library) for e in meal.entries],
                    )
                    for meal in day.meals()
                ],
                totals=_totals(day.cost, day.macros),
            )
        )
    totals = (
        _totals(logged.total_cost, logged.total_macros)
        if logged is not None
        else _totals(0.0, MacrosInfo.zero())
    )
    return DiaryWeek(week=week, exists=dto is not None, days=days, totals=totals)


def create_app(data_dir: Path, recipes_dir: Path, diary_dir: Path) -> FastAPI:
    """Build the diary server over explicit directories (no CWD fallback)."""
    data_dir, recipes_dir, diary_dir = (
        Path(data_dir),
        Path(recipes_dir),
        Path(diary_dir),
    )
    for label, path in (
        ("data_dir", data_dir),
        ("recipes_dir", recipes_dir),
    ):
        if not path.is_dir():
            raise FileNotFoundError(f"{label} does not exist: {path}")

    library = load_library(data_dir, recipes_dir)
    state = _State()
    state.library = library
    state.diary_dir = diary_dir

    recipe_cards = {
        (r.category.value, r.id): renderer.render_recipe_card(r)
        for r in library.recipes.values()
    }
    ingredient_cards = {
        (i.aisle.value, i.id): render_ingredient_card(i)
        for i in library.ingredients.values()
    }

    app = FastAPI(title="Meal Prep Diary")

    @app.middleware("http")
    async def access_log(request: Request, call_next: Any) -> Response:
        started = time.perf_counter()
        response = cast("Response", await call_next(request))
        elapsed_ms = (time.perf_counter() - started) * 1000
        if response.status_code >= 500:
            logger.error(
                "%s %s -> %d (%.1fms)",
                request.method,
                request.url.path,
                response.status_code,
                elapsed_ms,
            )
        elif response.status_code >= 400:
            logger.warning(
                "%s %s -> %d (%.1fms)",
                request.method,
                request.url.path,
                response.status_code,
                elapsed_ms,
            )
        else:
            logger.info(
                "%s %s -> %d (%.1fms)",
                request.method,
                request.url.path,
                response.status_code,
                elapsed_ms,
            )
        return response

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/version")
    def version() -> dict[str, str]:
        # Set by the image build (Dockerfile); "dev" when run from a checkout.
        return {
            "version": os.environ.get("MEAL_PREP_VERSION", "dev"),
            "commit": os.environ.get("MEAL_PREP_COMMIT", "unknown"),
        }

    @app.get("/api/week/current")
    def week_current() -> dict[str, str]:
        return {"week": current_week()}

    @app.get("/api/catalog")
    def catalog() -> dict[str, Any]:
        groups: dict[str, list[CatalogEntry]] = {c.value: [] for c in RecipeCategory}
        for recipe in library.recipes.values():
            macros = recipe.per_serving_macros
            groups[recipe.category.value].append(
                CatalogEntry(
                    id=recipe.id,
                    title=recipe.title,
                    category=recipe.category.value,
                    kcal=macros.calories_kcal,
                    protein_g=macros.protein_g,
                    carbs_g=macros.carbs_g,
                    fat_g=macros.fat_g,
                    cost=recipe.cost_per_portion,
                )
            )
        for entries in groups.values():
            entries.sort(key=lambda e: e.title)
        return {
            "groups": [
                {
                    "category": c.value,
                    "recipes": [e.model_dump() for e in groups[c.value]],
                }
                for c in RecipeCategory
            ]
        }

    # Entry operations read, change and write a whole week file; one lock keeps
    # two overlapping requests from losing each other's change.
    diary_lock = threading.Lock()

    def check_week(week: str) -> None:
        try:
            week_dates(week)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

    def read_week(week: str) -> DiaryWeekDTO | None:
        try:
            return load_diary_week(state.diary_dir, week)
        except FileNotFoundError:
            return None
        except ValueError as e:
            raise HTTPException(
                status_code=422, detail=f"invalid diary file for week '{week}': {e}"
            ) from e

    def write_week(week: str, dto: DiaryWeekDTO | None) -> None:
        if dto is None:
            delete_diary_week(state.diary_dir, week)
        else:
            save_diary_week(state.diary_dir, dto)

    @app.get("/api/diary/{week}")
    def diary_get(week: str) -> DiaryWeek:
        check_week(week)
        return _week_response(week, read_week(week), library)

    @app.post("/api/diary/{week}/entries")
    def entry_add(week: str, body: NewEntry) -> DiaryWeek:
        check_week(week)
        recipe = library.recipes.get(body.recipe)
        if recipe is None:
            raise HTTPException(
                status_code=422, detail=f"unknown recipe '{body.recipe}'"
            )
        with diary_lock:
            try:
                dto, entry = add_entry(
                    read_week(week),
                    week,
                    body.date,
                    body.mealtime,
                    recipe,
                    body.position,
                )
            except ValueError as e:
                raise HTTPException(status_code=422, detail=str(e)) from e
            write_week(week, dto)
        logger.info(
            "added %s to %s %s (%s)", recipe.id, body.date, body.mealtime, entry.id
        )
        return _week_response(week, dto, library)

    @app.delete("/api/diary/{week}/entries/{entry_id}")
    def entry_remove(week: str, entry_id: uuid.UUID) -> DiaryWeek:
        check_week(week)
        with diary_lock:
            current = read_week(week)
            if current is None:
                raise HTTPException(status_code=404, detail="no such entry")
            try:
                dto = remove_entry(current, entry_id)
            except EntryNotFoundError as e:
                raise HTTPException(status_code=404, detail=str(e)) from e
            write_week(week, dto)
        logger.info("removed entry %s from %s", entry_id, week)
        return _week_response(week, dto, library)

    @app.patch("/api/diary/{week}/entries/{entry_id}")
    def entry_move(week: str, entry_id: uuid.UUID, body: EntryPlacement) -> DiaryWeek:
        check_week(week)
        with diary_lock:
            current = read_week(week)
            if current is None:
                raise HTTPException(status_code=404, detail="no such entry")
            try:
                dto = move_entry(
                    current, entry_id, body.date, body.mealtime, body.position
                )
            except EntryNotFoundError as e:
                raise HTTPException(status_code=404, detail=str(e)) from e
            except ValueError as e:
                raise HTTPException(status_code=422, detail=str(e)) from e
            write_week(week, dto)
        logger.info("moved entry %s to %s %s", entry_id, body.date, body.mealtime.value)
        return _week_response(week, dto, library)

    @app.get("/cards/recipe/{category}/{slug}.html", response_class=HTMLResponse)
    def recipe_card(category: str, slug: str) -> str:
        try:
            return recipe_cards[(category, slug.removesuffix(".html"))]
        except KeyError:
            raise HTTPException(status_code=404, detail="unknown recipe card") from None

    @app.get("/cards/ingredient/{aisle}/{slug}.html", response_class=HTMLResponse)
    def ingredient_card(aisle: str, slug: str) -> str:
        try:
            return ingredient_cards[(aisle, slug.removesuffix(".html"))]
        except KeyError:
            raise HTTPException(
                status_code=404, detail="unknown ingredient card"
            ) from None

    ui_dir = Path(__file__).resolve().parent / "static"
    if ui_dir.is_dir():
        app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")

    return app
