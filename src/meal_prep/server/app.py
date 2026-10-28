"""FastAPI diary server: catalog, diary entries and prep sessions over flat
YAML files, plus the recipe/ingredient cards and the static UI.

``create_app`` wires the pieces: ``diary_routes`` and ``session_routes`` (edits
run by ``editing.Editor`` over ``store.DiaryStore``), ``week_view`` (the page
they return), ``cards``. The prep-session rules and editing modes
(``docs/prep-sessions.md``) live in ``meal_prep.services.prep``.
"""

from __future__ import annotations

import datetime
import logging
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles

from meal_prep.enums import RecipeCategory
from meal_prep.library import load_library
from meal_prep.server.api_models import CatalogEntry
from meal_prep.server.cards import cards_router
from meal_prep.server.diary_routes import diary_router
from meal_prep.server.editing import Editor
from meal_prep.server.session_routes import session_router
from meal_prep.server.store import DiaryStore
from meal_prep.server.weeks import current_week

logger = logging.getLogger("meal_prep.server")


def create_app(
    data_dir: Path,
    recipes_dir: Path,
    diary_dir: Path,
    today: Callable[[], datetime.date] = datetime.date.today,
) -> FastAPI:
    """Build the diary server over explicit directories (no CWD fallback).

    ``today`` splits Plan (after it) from Log (it and earlier); the server's
    local date unless a test pins it.
    """
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
    editor = Editor(library, DiaryStore(diary_dir), today)

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

    app.include_router(diary_router(editor))
    app.include_router(session_router(editor))
    app.include_router(cards_router(library))

    ui_dir = Path(__file__).resolve().parent / "static"
    if ui_dir.is_dir():
        app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")

    return app
