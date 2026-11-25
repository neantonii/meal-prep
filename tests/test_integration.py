"""Root-level integration tests over the real authored data.

Data-consistency smoke tests, not unit tests: enrich every ingredient, load the
whole library (every recipe and meal enriched), render cards and a solved week
plan. Most assert nothing about the values: if any authored file is malformed
the loader or a service raises and the test fails.
"""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from meal_prep import renderer
from meal_prep.adapters.ingredients import load_all_ingredients
from meal_prep.adapters.units import load_units
from meal_prep.enums import Mealtime
from meal_prep.library import load_library
from meal_prep.models.library import Library
from meal_prep.planner.archetypes import STANDARD
from meal_prep.planner.plan import Dish, Problem, Slot
from meal_prep.planner.solver import plan
from meal_prep.services.ingredients import prepare_catalog

_REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def library() -> Library:
    return load_library(_REPO_ROOT / "data", _REPO_ROOT / "recipes")


def test_all_ingredients_enrich_without_error():
    units = load_units(_REPO_ROOT / "data" / "units.yaml")
    dtos = load_all_ingredients(_REPO_ROOT / "data" / "ingredients")
    catalog = prepare_catalog(dtos, units)

    # No per-value assertions: merely that every authored ingredient enriched
    # without raising. This single guard only prevents a vacuous pass if the
    # catalog were accidentally empty.
    assert catalog


def test_library_loads_every_recipe_enriched(library: Library):
    # No per-value assertions: merely that every authored recipe enriched
    # without raising (unknown ingredient, unregistered unit, unknown
    # equipment, ...). These guards only prevent a vacuous pass.
    assert library.ingredients
    assert len(library.recipes) == len(list((_REPO_ROOT / "recipes").rglob("*.cook")))
    assert library.meals == {}


def test_library_mappings_are_read_only(library: Library):
    with pytest.raises(TypeError):
        library.recipes["new"] = library.recipes["air-fried-chicken-breast"]  # type: ignore[index]


def test_library_requires_existing_recipes_dir(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_library(_REPO_ROOT / "data", tmp_path / "no-such-dir")


def test_library_enriches_meals(tmp_path):
    meals_dir = tmp_path / "meals"
    meals_dir.mkdir()
    (meals_dir / "oatmeal-breakfast.yaml").write_text(
        "id: oatmeal-breakfast\n"
        "title: Oatmeal Breakfast\n"
        "recipes:\n"
        "  - blueberry-peanut-butter-overnight-oats\n"
        "  - boiled-eggs-with-mayo\n"
        "  - flat-white\n",
        encoding="utf-8",
    )

    library = load_library(_REPO_ROOT / "data", _REPO_ROOT / "recipes", meals_dir)

    meal = library.meals["oatmeal-breakfast"]
    assert meal.recipe_ids == (
        "blueberry-peanut-butter-overnight-oats",
        "boiled-eggs-with-mayo",
        "flat-white",
    )
    assert meal.recipes[0] is library.recipes["blueberry-peanut-butter-overnight-oats"]


def test_render_all_recipe_cards(tmp_path, library: Library):
    out_dir = tmp_path / "recipe_cards"
    out_dir.mkdir()

    # Plant a stale card that corresponds to no authored recipe; it must be
    # removed by the regeneration's force cleanup.
    stale = out_dir / "modular_carb" / "stale-deleted-recipe.html"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("<html>stale</html>", encoding="utf-8")

    generated = renderer.render_all_recipe_cards(library.recipes.values(), out_dir)

    # One card per authored recipe, and the stale card is gone.
    assert len(generated) == len(library.recipes)
    assert not stale.exists()

    # Every card landed at <category>/<slug>.html and is a non-empty HTML doc.
    for path in generated:
        assert path.is_relative_to(out_dir)
        content = path.read_text(encoding="utf-8")
        assert content.startswith("<!DOCTYPE html>")


def test_render_all_recipe_cards_missing_output_dir_raises(tmp_path, library: Library):
    with pytest.raises(FileNotFoundError):
        renderer.render_all_recipe_cards(
            library.recipes.values(), tmp_path / "no-such-dir"
        )


def test_air_fried_chicken_breast_totals(library: Library):
    """Golden totals for a real recipe: catch silent math/data regressions."""
    recipe = library.recipes["air-fried-chicken-breast"]

    assert recipe.total_cost == pytest.approx(10.91, abs=0.01)
    assert recipe.batch_macros.calories_kcal == pytest.approx(572.98, abs=0.01)
    assert recipe.per_serving_macros.protein_g == pytest.approx(54.86, abs=0.01)


def test_plan_a_week_from_the_library(library: Library):
    """The standard archetypes can be filled from the real recipes, and each
    slot comes out in its chosen archetype with no misfit."""
    thursday = datetime.date(2026, 11, 5)
    slots = tuple(
        Slot(date=thursday + datetime.timedelta(days=d), mealtime=m, cycle=thursday)
        for d in range(3)
        for m in Mealtime
    )
    problem = Problem(
        slots=slots,
        history=(),
        pins=(),
        batches=(),
        sessions=(thursday,),
        archetypes=dict(STANDARD),
    )
    result = plan(list(library.recipes.values()), problem)
    filled = {(p.date, p.mealtime) for p in result.placements}
    assert filled == {(s.date, s.mealtime) for s in slots}
    assert dict(result.points)["archetype fit"] < 3  # base costs at most


def test_every_archetype_role_has_a_recipe(library: Library):
    """Archetypes name categories and meal roles, never recipes: each role
    must still find a recipe in the library (a typo or a retired role would
    leave a part of a meal that can never be filled)."""
    dishes = [Dish(r.category, r.meal_role) for r in library.recipes.values()]
    for mealtime, archetypes in STANDARD.items():
        for archetype in archetypes:
            for role in archetype.roles:
                if role.takeout:
                    continue
                assert any(role.accepts("", d) for d in dishes), (
                    f"{mealtime} {archetype.name}: no recipe plays {role.name}"
                )
