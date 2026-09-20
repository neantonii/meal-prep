from pathlib import Path
from meal_prep.models.units import load_units
from meal_prep.models.equipment import load_equipment
from meal_prep.models.ingredient import load_all_ingredients
from meal_prep.models.recipe import load_recipe_file
from meal_prep.renderer import render_recipe_card_html


def test_render_recipe_card_html():
    units = load_units(Path("data/units.yaml"))
    equipment = load_equipment(Path("data/equipment.yaml"))
    catalog = load_all_ingredients(Path("data/ingredients"))

    recipe = load_recipe_file(
        Path("recipes/modular_protein/air-fried-chicken-breast.cook"),
        catalog=catalog,
        equipment_reg=equipment,
        units_reg=units,
    )

    html = render_recipe_card_html(recipe, catalog, equipment, units)

    assert "<title>Air-Fried Seasoned Chicken Breast — Meal Prep Recipe</title>" in html
    assert "Per-Serving Nutrition" in html
    assert "🛒 Ingredients" in html
    assert "Boneless, Skinless Chicken Breast" in html
    assert "Extra Virgin Olive Oil" in html
    assert "Coarse Kosher Salt" in html
    assert "Ground Black Pepper" in html
    assert "Garlic Powder" in html
    assert "Smoked Paprika" in html
    assert "badge-cookware" in html
    assert "Air Fryer" in html
    assert "Meat Thermometer" in html
    assert "badge-timer" in html
    assert "16 min" in html
    assert "5 min" in html
    # Cooking Loss removed
    assert "Cooking Loss" not in html
    # Sat Fat and Sugars present
    assert "Sat Fat" in html
    assert "Sugars" in html


def test_render_all_recipe_cards(tmp_path):
    from meal_prep.renderer import render_all_recipe_cards

    out_dir = tmp_path / "recipe_cards"
    generated = render_all_recipe_cards(
        recipes_dir=Path("recipes"),
        output_dir=out_dir,
    )
    assert len(generated) >= 1
    target = out_dir / "modular_protein" / "air-fried-chicken-breast.html"
    assert target.exists()
    assert target in generated
    content = target.read_text(encoding="utf-8")
    assert "Air-Fried Seasoned Chicken Breast" in content
    assert "Cooking Loss" not in content
    assert "Sat Fat" in content
    assert "Sugars" in content
