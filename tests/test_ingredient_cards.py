"""Tests for the ingredient card renderer (``meal_prep.ingredient_cards``)."""

from __future__ import annotations

from meal_prep import renderer
from meal_prep.enums import Aisle, StorageType
from meal_prep.ingredient_cards import render_ingredient_card
from meal_prep.models.ingredient import Ingredient
from tests.test_renderer import _macros


def _ingredient() -> Ingredient:
    from meal_prep.engines.conversion_graph import ConversionEdge, build_graph

    return Ingredient(
        id="rolled-oats",
        name="Rolled Oats",
        step_name="oats",
        aisle=Aisle.PANTRY,
        storage=StorageType.AMBIENT,
        shelf_life_days=365,
        brand="Bulk",
        product="Rolled Oats 1kg",
        price=4.99,
        macros_per_100g=_macros(),
        custom_units=frozenset(),
        synonyms={},
        conversion_graph=build_graph(
            [ConversionEdge("cup", "g", 90.0), ConversionEdge("package", "g", 1000.0)]
        ),
        package_weight_g=1000.0,
        price_per_100g=0.499,
    )


def test_ingredient_card_shows_catalog_facts():
    card = render_ingredient_card(_ingredient())
    assert "Rolled Oats" in card
    assert "Pantry" in card
    assert "$4.99" in card
    assert "1000 g" in card
    assert "1 cup = 90 g" in card


def test_recipe_card_links_ingredients_when_dir_given():
    from tests.test_renderer import _recipe

    plain = renderer.render_recipe_card(_recipe())
    assert "ingredient_cards" not in plain
    linked = renderer.render_recipe_card(_recipe(), "../ingredient_cards")
    assert "../ingredient_cards/meat/boneless-chicken-breast.html" in linked
