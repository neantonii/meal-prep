"""Recipe and ingredient cards, rendered once at startup and served as HTML."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from meal_prep import renderer
from meal_prep.ingredient_cards import render_ingredient_card
from meal_prep.models.library import Library


def cards_router(library: Library) -> APIRouter:
    router = APIRouter(prefix="/cards")
    recipe_cards = {
        (r.category.value, r.id): renderer.render_recipe_card(r)
        for r in library.recipes.values()
    }
    ingredient_cards = {
        (i.aisle.value, i.id): render_ingredient_card(i)
        for i in library.ingredients.values()
    }

    @router.get("/recipe/{category}/{slug}.html", response_class=HTMLResponse)
    def recipe_card(category: str, slug: str) -> str:
        try:
            return recipe_cards[(category, slug.removesuffix(".html"))]
        except KeyError:
            raise HTTPException(status_code=404, detail="unknown recipe card") from None

    @router.get("/ingredient/{aisle}/{slug}.html", response_class=HTMLResponse)
    def ingredient_card(aisle: str, slug: str) -> str:
        try:
            return ingredient_cards[(aisle, slug.removesuffix(".html"))]
        except KeyError:
            raise HTTPException(
                status_code=404, detail="unknown ingredient card"
            ) from None

    return router
