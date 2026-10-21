"""FastAPI diary server: catalog + week editor API over flat YAML files."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from meal_prep import renderer
from meal_prep.adapters.logs import delete_log_week, load_log_week, save_log_week
from meal_prep.dtos.log import LogWeekDTO
from meal_prep.enums import Mealtime, RecipeCategory
from meal_prep.ingredient_cards import render_ingredient_card
from meal_prep.library import MealPrepLibrary
from meal_prep.models.recipe import Recipe
from meal_prep.server.weeks import current_week, week_dates
from meal_prep.services.logs import prepare_log_week
from meal_prep.services.recipes import prepare_recipe

logger = logging.getLogger("meal_prep.server")


class _State:
    library: MealPrepLibrary
    prepared: dict[str, Recipe]
    diary_dir: Path


class CatalogEntry(BaseModel):
    id: str
    title: str
    category: str
    kcal: float
    protein_g: float
    cost: float


class DiaryMeal(BaseModel):
    mealtime: str
    recipes: list[str]


class DiaryDay(BaseModel):
    date: str
    meals: list[DiaryMeal]


class DiaryWeek(BaseModel):
    week: str
    exists: bool
    days: list[DiaryDay]
    totals: dict[str, float]


def _totals(week: str, dto: LogWeekDTO, state: _State) -> dict[str, float]:
    enriched = prepare_log_week(dto, state.prepared)
    m = enriched.total_macros
    return {
        "kcal": m.calories_kcal,
        "protein_g": m.protein_g,
        "carbs_g": m.carbs_g,
        "fat_g": m.fat_g,
        "fiber_g": m.fiber_g,
        "cost": enriched.total_cost,
    }


def _dto_to_response(week: str, dto: LogWeekDTO, *, exists: bool) -> DiaryWeek:
    days = [
        DiaryDay(
            date=str(d.date),
            meals=[
                DiaryMeal(mealtime=mt.value, recipes=list(getattr(d, mt.value) or []))
                for mt in Mealtime
                if getattr(d, mt.value) is not None
            ],
        )
        for d in dto.days
    ]
    return DiaryWeek(week=week, exists=exists, days=days, totals={})


def _scaffold_response(week: str) -> DiaryWeek:
    return DiaryWeek(
        week=week,
        exists=False,
        days=[DiaryDay(date=d.isoformat(), meals=[]) for d in week_dates(week)],
        totals={},
    )


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

    library = MealPrepLibrary.load(data_dir, recipes_dir)
    prepared = {
        rid: prepare_recipe(dto, library.catalog, library.equipment)
        for rid, dto in library.recipes.items()
    }
    state = _State()
    state.library = library
    state.prepared = prepared
    state.diary_dir = diary_dir

    recipe_cards = {
        (r.category.value, r.id): renderer.render_recipe_card(r)
        for r in prepared.values()
    }
    ingredient_cards = {
        (i.aisle.value, i.id): render_ingredient_card(i)
        for i in library.catalog.values()
    }

    app = FastAPI(title="Meal Prep Diary")

    @app.middleware("http")
    async def access_log(request: Request, call_next: Any) -> Response:
        started = time.perf_counter()
        try:
            response = cast("Response", await call_next(request))
        except Exception:
            logger.exception("%s %s -> 500", request.method, request.url.path)
            raise
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

    @app.get("/api/week/current")
    def week_current() -> dict[str, str]:
        return {"week": current_week()}

    @app.get("/api/catalog")
    def catalog() -> dict[str, Any]:
        groups: dict[str, list[CatalogEntry]] = {c.value: [] for c in RecipeCategory}
        for recipe in prepared.values():
            macros = recipe.per_serving_macros
            groups[recipe.category.value].append(
                CatalogEntry(
                    id=recipe.id,
                    title=recipe.title,
                    category=recipe.category.value,
                    kcal=macros.calories_kcal,
                    protein_g=macros.protein_g,
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

    @app.get("/api/diary/{week}")
    def diary_get(week: str) -> JSONResponse:
        try:
            week_dates(week)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        try:
            dto = load_log_week(state.diary_dir, week)
        except FileNotFoundError:
            return JSONResponse(_scaffold_response(week).model_dump())
        try:
            totals = _totals(week, dto, state)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        body = _dto_to_response(week, dto, exists=True)
        body.totals = totals
        return JSONResponse(body.model_dump())

    @app.post("/api/diary/{week}")
    def diary_save(week: str, payload: dict[str, Any]) -> JSONResponse:
        try:
            dates = week_dates(week)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        if payload.get("week", week) != week:
            raise HTTPException(
                status_code=422, detail=f"payload week does not match URL week '{week}'"
            )
        try:
            dto = LogWeekDTO.model_validate(payload)
        except Exception as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        if dto.week != week:
            raise HTTPException(
                status_code=422, detail=f"payload week does not match URL week '{week}'"
            )
        allowed = {d.isoformat() for d in dates}
        actual = [str(d.date) for d in dto.days]
        if any(day not in allowed for day in actual):
            raise HTTPException(
                status_code=422,
                detail=f"day dates {actual} fall outside week {week}",
            )
        try:
            totals = _totals(week, dto, state)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        save_log_week(state.diary_dir, dto)
        n_recipes = sum(
            len(getattr(d, m.value) or []) for d in dto.days for m in Mealtime
        )
        logger.info("saved week %s (%d recipes)", week, n_recipes)
        body = _dto_to_response(week, dto, exists=True)
        body.totals = totals
        return JSONResponse(body.model_dump())

    @app.delete("/api/diary/{week}", status_code=204)
    def diary_delete(week: str) -> Response:
        try:
            week_dates(week)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        deleted = delete_log_week(state.diary_dir, week)
        logger.info("deleted week %s (existed=%s)", week, deleted)
        return Response(status_code=204)

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
