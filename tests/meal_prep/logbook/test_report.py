"""Tests for the logbook HTML report (``meal_prep/logbook``)."""

from __future__ import annotations

from datetime import date

from meal_prep.enums import RecipeCategory
from meal_prep.logbook import render_log_week, render_log_week_page
from meal_prep.models.ingredient import MacrosInfo
from meal_prep.models.log import LogDay, LogWeek
from meal_prep.models.recipe import Recipe


def _macros(*, cal: float = 100.0, protein: float = 10.0) -> MacrosInfo:
    return MacrosInfo(
        calories_kcal=cal,
        protein_g=protein,
        fat_g=5.0,
        carbs_g=20.0,
        fiber_g=1.0,
        saturated_fat_g=0.0,
        sugars_g=0.0,
        sodium_mg=0.0,
        potassium_mg=0.0,
    )


def _recipe(recipe_id: str = "oatmeal") -> Recipe:
    return Recipe(
        id=recipe_id,
        title="Oatmeal",
        category=RecipeCategory.BREAKFAST,
        servings=1.0,
        cooked_g=300.0,
        fridge_days=2,
        freezer_friendly=False,
        equipment=(),
        cookware_by_token={},
        ingredients=(),
        instructions="Cook.",
    )


def _week() -> LogWeek:
    recipe = _recipe()
    day = LogDay(date=date(2026, 10, 13), breakfast=(recipe, recipe))
    return LogWeek(week="2026-W42", days=(day, day))


def test_report_is_standalone_html_with_totals():
    page = render_log_week(_week())
    assert page.startswith("<!DOCTYPE html>")
    assert "Eating Log · 2026-W42" in page
    assert "2026-10-13" in page
    assert "Breakfast" in page
    assert "<table" in page
    assert page.count('class="day-cell"') == 2


def test_report_links_recipe_cards_when_lookup_and_dir_given():
    page = render_log_week(
        _week(), recipes={"oatmeal": _recipe()}, cards_dir="recipe_cards"
    )
    assert "recipe_cards/breakfast/oatmeal.html" in page


def test_report_renders_plain_titles_without_cards_dir():
    page = render_log_week(_week(), recipes={"oatmeal": _recipe()})
    assert "Oatmeal" in page
    assert "recipe_cards" not in page


def test_report_renders_plain_titles_without_lookup():
    page = render_log_week(_week())
    assert "Oatmeal" in page
    assert "recipe_cards" not in page


def test_page_relativizes_card_links_to_output_dir(tmp_path):
    out = tmp_path / "weekly_plan" / "log-2026-W42.html"
    render_log_week_page(
        _week(),
        out,
        recipes={"oatmeal": _recipe()},
        cards_dir=tmp_path / "recipe_cards",
    )
    assert "../recipe_cards/breakfast/oatmeal.html" in out.read_text()
