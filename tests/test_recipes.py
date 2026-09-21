import json
from pathlib import Path
import pytest
import jsonschema
from meal_prep.models.enums import RecipeCategory, StorageType
from meal_prep.models.units import load_units
from meal_prep.models.equipment import load_equipment
from meal_prep.models.ingredient import Ingredient, load_all_ingredients
from meal_prep.models.recipe import (
    Recipe,
    RecipeFrontmatter,
    RecipeYield,
    RecipeStorage,
    parse_cooklang_body,
    split_recipe_file,
    load_recipe_file,
    load_all_recipes,
)


@pytest.fixture
def units():
    return load_units(Path("data/units.yaml"))


@pytest.fixture
def equipment():
    return load_equipment(Path("data/equipment.yaml"))


@pytest.fixture
def mock_catalog(units):
    """Catalog with chicken breast, olive oil, and spices."""
    chicken = Ingredient.model_validate(
        {
            "id": "boneless-chicken-breast",
            "name": "Boneless Chicken Breast",
            "aisle": "meat",
            "storage": "refrigerated",
            "shelf_life_days": 3,
            "package": {
                "container": "pack",
                "unit": "piece",
                "amount": 4,
                "container_weight_g": 950.0,
            },
            "reference": {
                "brand": "Compliments",
                "product": "Chicken Breast",
                "price": 20.50,
            },
            "macros_per_100g": {
                "calories_kcal": 110.0,
                "protein_g": 23.0,
                "fat_g": 2.5,
                "saturated_fat_g": 0.5,
                "carbs_g": 0.0,
                "fiber_g": 0.0,
                "sugars_g": 0.0,
                "sodium_mg": 45.0,
                "potassium_mg": 350.0,
            },
            "conversions": [{"from": "piece", "to": "g", "factor": 237.5}],
        }
    )
    olive_oil = Ingredient.model_validate(
        {
            "id": "olive-oil",
            "name": "Extra Virgin Olive Oil",
            "aisle": "pantry",
            "storage": "ambient",
            "shelf_life_days": 365,
            "package": {
                "container": "bottle",
                "unit": "ml",
                "amount": 1000,
                "container_weight_g": 920.0,
            },
            "reference": {
                "brand": "Longo's Essentials",
                "product": "Extra Virgin Olive Oil 1L",
                "price": 11.99,
            },
            "macros_per_100g": {
                "calories_kcal": 884.0,
                "protein_g": 0.0,
                "fat_g": 100.0,
                "carbs_g": 0.0,
                "fiber_g": 0.0,
            },
            "conversions": [{"from": "ml", "to": "g", "factor": 0.92}],
        }
    )
    salt = Ingredient.model_validate(
        {
            "id": "kosher-salt",
            "name": "Coarse Kosher Salt",
            "aisle": "spices",
            "storage": "ambient",
            "shelf_life_days": 730,
            "package": {
                "container": "box",
                "unit": "g",
                "amount": 1000,
                "container_weight_g": 1000.0,
            },
            "reference": {
                "brand": "Windsor",
                "product": "Kosher Salt 1kg",
                "price": 4.49,
            },
            "macros_per_100g": {
                "calories_kcal": 0.0,
                "protein_g": 0.0,
                "fat_g": 0.0,
                "carbs_g": 0.0,
                "fiber_g": 0.0,
                "sodium_mg": 39000.0,
            },
            "conversions": [{"from": "tsp", "to": "g", "factor": 5.0}],
        }
    )
    catalog = {
        "boneless-chicken-breast": chicken,
        "olive-oil": olive_oil,
        "kosher-salt": salt,
    }
    for item in catalog.values():
        item.get_conversion_graph(units)
    return catalog


def test_recipe_json_schemas_exist_and_are_valid():
    frontmatter_schema_path = Path("schemas/recipe_frontmatter.schema.json")
    recipes_schema_path = Path("schemas/recipes.schema.json")

    assert frontmatter_schema_path.exists()
    assert recipes_schema_path.exists()

    with frontmatter_schema_path.open("r", encoding="utf-8") as f:
        fm_schema = json.load(f)
    with recipes_schema_path.open("r", encoding="utf-8") as f:
        r_schema = json.load(f)

    assert "RecipeCategory" in fm_schema.get("$defs", {})
    assert "RecipeYield" in fm_schema.get("$defs", {})
    assert "RecipeStorage" in fm_schema.get("$defs", {})

    assert "RecipeIngredientRef" in r_schema.get("$defs", {})
    assert "RecipeCookwareRef" in r_schema.get("$defs", {})
    assert "RecipeTimerRef" in r_schema.get("$defs", {})


def test_parse_cooklang_body_clean():
    text = (
        "Trim fat from @boneless-chicken-breast{4%piece}. "
        "Place uncovered on #wire-rack for ~surface-drying{1%hr}. "
        "Rub with @olive-oil{1%tbsp} and season with @kosher-salt{1%tsp}. "
        "Cook in #air-fryer for ~air-fry-time{16%min} until internal temp reaches 74C checked with #meat-thermometer. "
        "Rest for ~rest-time{5%min}."
    )

    ingredients, cookware, timers = parse_cooklang_body(text)

    # Ingredients
    assert len(ingredients) == 3
    assert ingredients[0].id == "boneless-chicken-breast"
    assert ingredients[0].quantity == 4.0
    assert ingredients[0].unit == "piece"

    assert ingredients[1].id == "olive-oil"
    assert ingredients[1].quantity == 1.0
    assert ingredients[1].unit == "tbsp"

    assert ingredients[2].id == "kosher-salt"
    assert ingredients[2].quantity == 1.0
    assert ingredients[2].unit == "tsp"

    # Cookware
    cookware_ids = [cw.id for cw in cookware]
    assert "wire-rack" in cookware_ids
    assert "air-fryer" in cookware_ids
    assert "meat-thermometer" in cookware_ids

    # Timers
    assert len(timers) == 3
    assert timers[0].name == "surface-drying"
    assert timers[0].duration == 1.0
    assert timers[0].unit == "hr"

    assert timers[1].name == "air-fry-time"
    assert timers[1].duration == 16.0
    assert timers[1].unit == "min"

    assert timers[2].name == "rest-time"
    assert timers[2].duration == 5.0
    assert timers[2].unit == "min"


def test_parse_cooklang_missing_quantity_or_unit_fails():
    with pytest.raises(ValueError, match="missing quantity or unit"):
        parse_cooklang_body("Season with @kosher-salt in bowl.")


def test_split_recipe_file_valid():
    content = """---
id: air-fried-chicken-breast
title: Air-Dried / Air-Fried Chicken Breast
category: modular_protein
yield:
  servings: 4
  cooked_g: 660
storage:
  fridge_days: 4
  freezer_friendly: true
equipment:
  - air-fryer
  - meat-thermometer
  - wire-rack
---

Trim fat from @boneless-chicken-breast{4%piece}.
"""
    raw_frontmatter, instructions = split_recipe_file(content)
    assert raw_frontmatter["id"] == "air-fried-chicken-breast"
    assert raw_frontmatter["yield"]["servings"] == 4
    assert raw_frontmatter["yield"]["cooked_g"] == 660
    assert instructions == "Trim fat from @boneless-chicken-breast{4%piece}."

    # Validate against JSON schema
    schema_path = Path("schemas/recipe_frontmatter.schema.json")
    with schema_path.open("r", encoding="utf-8") as f:
        schema = json.load(f)
    jsonschema.validate(instance=raw_frontmatter, schema=schema)


def test_load_recipe_file_complete_and_computations(tmp_path, mock_catalog, equipment, units):
    cat_dir = tmp_path / "modular_protein"
    cat_dir.mkdir()
    cook_file = cat_dir / "air-fried-chicken-breast.cook"

    cook_file.write_text(
        """---
id: air-fried-chicken-breast
title: Air-Dried / Air-Fried Chicken Breast
category: modular_protein
yield:
  servings: 4
  cooked_g: 660
storage:
  fridge_days: 4
  freezer_friendly: true
equipment:
  - air-fryer
  - meat-thermometer
  - wire-rack
---

Trim @boneless-chicken-breast{4%piece}. Place on #wire-rack for ~surface-drying{1%hr}.
Rub with @olive-oil{1%tbsp} and @kosher-salt{1%tsp}.
Cook in #air-fryer for ~air-fry-time{16%min} using #meat-thermometer.
""",
        encoding="utf-8",
    )

    recipe = load_recipe_file(
        cook_file,
        catalog=mock_catalog,
        equipment_reg=equipment,
        units_reg=units,
    )

    assert recipe.id == "air-fried-chicken-breast"
    assert recipe.title == "Air-Dried / Air-Fried Chicken Breast"
    assert recipe.category == RecipeCategory.MODULAR_PROTEIN
    assert recipe.portion_cooked_weight_g == 165.0  # 660 / 4

    # 1. Raw batch weight:
    # 4 pieces chicken = 4 * 237.5 = 950.0 g
    # 1 tbsp olive oil = 15 ml * 0.92 = 13.8 g
    # 1 tsp kosher salt = 5.0 g
    # Total = 950 + 13.8 + 5.0 = 968.8 g
    raw_weight = recipe.compute_raw_batch_weight_g(mock_catalog, units)
    assert raw_weight == 968.8

    # 2. Cooking loss %:
    # (1 - (660 / 968.8)) * 100 = 31.9%
    loss = recipe.compute_cooking_loss_percent(mock_catalog, units)
    assert loss == pytest.approx(31.9, abs=0.1)

    # 3. Cost calculation:
    # Chicken: 950g @ $20.50 / 950g = $20.50
    # Olive oil: 13.8g @ $11.99 / 920g ($1.303 / 100g) = $0.18
    # Salt: 5.0g @ $4.49 / 1000g ($0.449 / 100g) = $0.02
    # Total batch cost = $20.72
    batch_cost, serving_cost = recipe.compute_cost(mock_catalog, units)
    assert batch_cost == 20.72
    assert serving_cost == 5.18  # 20.72 / 4

    # 4. Macros calculation:
    batch_macros, serving_macros = recipe.compute_macros(mock_catalog, units)
    # Chicken 950g: 9.5 * 110 kcal = 1045 kcal, 9.5 * 23 = 218.5g protein
    # Olive oil 13.8g: 0.138 * 884 = 122 kcal, 0.138 * 100 = 13.8g fat
    # Batch calories ~ 1167 kcal
    assert batch_macros.calories_kcal == pytest.approx(1167.0, abs=1.0)
    assert serving_macros.calories_kcal == pytest.approx(291.8, abs=1.0)
    assert serving_macros.protein_g == pytest.approx(54.6, abs=0.5)

    # 5. Safe fridge storage window:
    # Recipe declares 4 days, chicken shelf life is 3 days -> min is 3 days!
    assert recipe.compute_safe_fridge_days(mock_catalog) == 3


def test_recipe_semantic_validation_errors(tmp_path, mock_catalog, equipment, units):
    cat_dir = tmp_path / "modular_protein"
    cat_dir.mkdir()

    # 1. Unknown equipment in frontmatter
    cook_file1 = cat_dir / "bad-equipment.cook"
    cook_file1.write_text(
        """---
id: bad-equipment
title: Bad Equipment
category: modular_protein
yield:
  servings: 1
  cooked_g: 100
storage:
  fridge_days: 2
  freezer_friendly: false
equipment:
  - futuristic-laser-cooker
---
Use @boneless-chicken-breast{1%piece}.
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown equipment ID"):
        load_recipe_file(cook_file1, catalog=mock_catalog, equipment_reg=equipment, units_reg=units)

    # 2. Unknown ingredient in body
    cook_file2 = cat_dir / "bad-ingredient.cook"
    cook_file2.write_text(
        """---
id: bad-ingredient
title: Bad Ingredient
category: modular_protein
yield:
  servings: 1
  cooked_g: 100
storage:
  fridge_days: 2
  freezer_friendly: false
equipment:
  - air-fryer
---
Use @alien-meat{100%g} with #air-fryer.
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="does not exist in ingredients catalog"):
        load_recipe_file(cook_file2, catalog=mock_catalog, equipment_reg=equipment, units_reg=units)

    # 3. Invalid timer unit
    cook_file3 = cat_dir / "bad-timer.cook"
    cook_file3.write_text(
        """---
id: bad-timer
title: Bad Timer
category: modular_protein
yield:
  servings: 1
  cooked_g: 100
storage:
  fridge_days: 2
  freezer_friendly: false
equipment:
  - air-fryer
---
Use @boneless-chicken-breast{1%piece}. Cook for ~timer{10%lightyears} with #air-fryer.
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="invalid time unit"):
        load_recipe_file(cook_file3, catalog=mock_catalog, equipment_reg=equipment, units_reg=units)

    # 4. Inconvertible unit for ingredient (e.g. chicken in cups without density bridge)
    cook_file4 = cat_dir / "bad-unit.cook"
    cook_file4.write_text(
        """---
id: bad-unit
title: Bad Unit
category: modular_protein
yield:
  servings: 1
  cooked_g: 100
storage:
  fridge_days: 2
  freezer_friendly: false
equipment:
  - air-fryer
---
Use @boneless-chicken-breast{2%cup} with #air-fryer.
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="cannot be converted to grams"):
        load_recipe_file(cook_file4, catalog=mock_catalog, equipment_reg=equipment, units_reg=units)


def test_load_real_recipes_from_disk(units, equipment):
    catalog = load_all_ingredients(Path("data/ingredients"))
    recipes = load_all_recipes(
        recipes_dir=Path("recipes"),
        catalog=catalog,
        equipment_reg=equipment,
        units_reg=units,
    )
    assert len(recipes) >= 1
    assert "air-fried-chicken-breast" in recipes
    chicken_recipe = recipes["air-fried-chicken-breast"]

    raw_g = chicken_recipe.compute_raw_batch_weight_g(catalog, units)
    assert raw_g > 900.0

    batch_cost, serving_cost = chicken_recipe.compute_cost(catalog, units)
    assert batch_cost > 0
    assert serving_cost > 0

    batch_macros, serving_macros = chicken_recipe.compute_macros(catalog, units)
    assert serving_macros.protein_g > 40.0
    assert serving_macros.calories_kcal > 200.0

