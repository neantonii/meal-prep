"""Root-level integration test: enrich the real ingredient catalog.

This is a data-consistency smoke test, not a unit test. It loads every authored
ingredient and enriches it via ``prepare_catalog``. It asserts nothing about the
values — if any ingredient is malformed (unregistered unit, missing gram path,
colliding custom-unit synonym, invalid conversion graph, ...) the service raises
and the test fails.
"""

from __future__ import annotations

from pathlib import Path

import renderer

from meal_prep.adapters.aisles import load_aisles
from meal_prep.adapters.ingredients import load_all_ingredients
from meal_prep.adapters.units import load_units
from meal_prep.library import MealPrepLibrary
from meal_prep.planner.report import render_week_plan_page
from meal_prep.planner.solver import plan_week
from meal_prep.services.ingredients import prepare_catalog
from meal_prep.services.recipes import prepare_recipe

_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_all_ingredients_enrich_without_error():
    units = load_units(_REPO_ROOT / "data" / "units.yaml")
    aisles = load_aisles(_REPO_ROOT / "data" / "aisles.yaml")
    dtos = load_all_ingredients(_REPO_ROOT / "data" / "ingredients")
    catalog = prepare_catalog(dtos, units, {a.id: a for a in aisles})

    # No per-value assertions: merely that every authored ingredient enriched
    # without raising. This single guard only prevents a vacuous pass if the
    # catalog were accidentally empty.
    assert catalog


def test_all_recipes_prepare_without_error():
    library = MealPrepLibrary.load(
        data_dir=_REPO_ROOT / "data",
        recipes_dir=_REPO_ROOT / "recipes",
    )

    prepared = {
        recipe_id: prepare_recipe(recipe, library.catalog, library.equipment)
        for recipe_id, recipe in library.recipes.items()
    }

    # No per-value assertions: merely that every authored recipe prepared
    # without raising (unknown ingredient, unregistered unit, unknown
    # equipment, ...). This guard only prevents a vacuous pass on an empty set.
    assert prepared


def test_render_all_recipe_cards():
    library = MealPrepLibrary.load(
        data_dir=_REPO_ROOT / "data",
        recipes_dir=_REPO_ROOT / "recipes",
    )

    out_dir = _REPO_ROOT / "recipe_cards"

    # Plant a stale card that corresponds to no authored recipe; it must be
    # removed by the regeneration's force cleanup.
    stale = out_dir / "modular_carb" / "stale-deleted-recipe.html"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("<html>stale</html>", encoding="utf-8")

    generated = renderer.render_all_recipe_cards(library, out_dir)

    # One card per authored recipe, and the stale card is gone.
    assert len(generated) == len(library.recipes)
    assert not stale.exists()

    # Every card landed at <category>/<slug>.html and is a non-empty HTML doc.
    for path in generated:
        assert path.is_relative_to(out_dir)
        content = path.read_text(encoding="utf-8")
        assert content.startswith("<!DOCTYPE html>")


def test_solve_week_plan_and_render_page():
    library = MealPrepLibrary.load(
        data_dir=_REPO_ROOT / "data",
        recipes_dir=_REPO_ROOT / "recipes",
    )
    prepared = {
        recipe_id: prepare_recipe(recipe, library.catalog, library.equipment)
        for recipe_id, recipe in library.recipes.items()
    }

    plan = plan_week(list(prepared.values()))
    assert len(plan.days) == 7

    target = render_week_plan_page(
        plan, _REPO_ROOT / "weekly_plan" / "plan.html", recipes=prepared
    )
    content = target.read_text(encoding="utf-8")
    assert content.startswith("<!DOCTYPE html>")
    assert content.count('class="day-card"') == 7
