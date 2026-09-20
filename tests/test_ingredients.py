import json
from pathlib import Path
import pytest
import yaml
import jsonschema
from pydantic import ValidationError
from meal_prep.models.enums import StorageType
from meal_prep.models.aisle import load_aisles
from meal_prep.models.units import load_units
from meal_prep.models.ingredient import (
    Ingredient,
    PackageInfo,
    ReferenceInfo,
    MacrosInfo,
    UnitConversion,
    load_ingredients_file,
    load_all_ingredients,
)


def test_load_meat_yaml():
    ingredients = load_ingredients_file(Path("data/ingredients/meat.yaml"))
    assert len(ingredients) >= 1

    chicken = ingredients[0]
    assert chicken.id == "boneless-chicken-breast"
    assert chicken.name == "Boneless, Skinless Chicken Breast"
    assert chicken.aisle == "meat"
    assert chicken.storage == StorageType.REFRIGERATED
    assert chicken.shelf_life_days == 3

    # Package validation
    assert chicken.package.container == "pack"
    assert chicken.package.unit == "piece"
    assert chicken.package.amount == 4
    assert chicken.package.container_weight_g == 950.0

    # Pricing & Calculated unit prices
    assert chicken.reference.brand == "Compliments"
    assert chicken.reference.price == 22.60
    assert chicken.price_per_100g == 2.38
    assert chicken.price_per_kg == 23.80
    assert chicken.price_per_unit == 5.65

    # Macros
    assert chicken.macros_per_100g.calories_kcal == 110.0
    assert chicken.macros_per_100g.protein_g == 23.0
    assert chicken.macros_per_100g.fat_g == 2.5
    assert chicken.macros_per_100g.saturated_fat_g == 0.5
    assert chicken.macros_per_100g.sugars_g == 0.0
    assert chicken.macros_per_100g.sodium_mg == 45.0
    assert chicken.macros_per_100g.potassium_mg == 350.0

    # Conversions
    assert chicken.get_conversion_factor("piece") == 237.5
    assert chicken.get_conversion_factor("unknown_unit") is None


def test_load_all_ingredients_catalog():
    catalog = load_all_ingredients(Path("data/ingredients"))
    assert "boneless-chicken-breast" in catalog
    assert catalog["boneless-chicken-breast"].aisle == "meat"


def test_aisle_file_mismatch_raises_error(tmp_path):
    bad_file = tmp_path / "produce.yaml"
    bad_file.write_text(
        """
- id: bad-chicken
  name: Chicken in Produce
  aisle: meat
  storage: refrigerated
  shelf_life_days: 3
  package:
    container: pack
    unit: piece
    amount: 1
    container_weight_g: 500
  reference:
    brand: Test
    product: Test Product
    price: 10.00
  macros_per_100g:
    calories_kcal: 100
    protein_g: 20
    fat_g: 2
    carbs_g: 0
    fiber_g: 0
  conversions:
    - unit: piece
      g: 500
        """
    )
    with pytest.raises(ValueError, match="does not match file stem 'produce'"):
        load_ingredients_file(bad_file)


def test_invalid_storage_type_raises_error():
    with pytest.raises(ValidationError):
        Ingredient.model_validate(
            {
                "id": "test-item",
                "name": "Test Item",
                "aisle": "meat",
                "storage": "invalid_storage_mode",
                "shelf_life_days": 3,
                "package": {
                    "container": "pack",
                    "unit": "piece",
                    "amount": 1,
                    "container_weight_g": 500,
                },
                "reference": {"brand": "Test", "product": "Test", "price": 5.0},
                "macros_per_100g": {
                    "calories_kcal": 100,
                    "protein_g": 20,
                    "fat_g": 1,
                    "carbs_g": 0,
                    "fiber_g": 0,
                },
                "conversions": [{"unit": "piece", "g": 500}],
            }
        )


def test_missing_mandatory_shelf_life_raises_error():
    with pytest.raises(ValidationError):
        Ingredient.model_validate(
            {
                "id": "test-item",
                "name": "Test Item",
                "aisle": "meat",
                "storage": "refrigerated",
                "package": {
                    "container": "pack",
                    "unit": "piece",
                    "amount": 1,
                    "container_weight_g": 500,
                },
                "reference": {"brand": "Test", "product": "Test", "price": 5.0},
                "macros_per_100g": {
                    "calories_kcal": 100,
                    "protein_g": 20,
                    "fat_g": 1,
                    "carbs_g": 0,
                    "fiber_g": 0,
                },
                "conversions": [{"unit": "piece", "g": 500}],
            }
        )


def test_missing_mandatory_conversions_raises_error():
    with pytest.raises(ValidationError):
        Ingredient.model_validate(
            {
                "id": "test-item",
                "name": "Test Item",
                "aisle": "meat",
                "storage": "refrigerated",
                "shelf_life_days": 3,
                "package": {
                    "container": "pack",
                    "unit": "piece",
                    "amount": 1,
                    "container_weight_g": 500,
                },
                "reference": {"brand": "Test", "product": "Test", "price": 5.0},
                "macros_per_100g": {
                    "calories_kcal": 100,
                    "protein_g": 20,
                    "fat_g": 1,
                    "carbs_g": 0,
                    "fiber_g": 0,
                },
                "conversions": [],  # empty list rejected by min_length=1
            }
        )


def test_ingredients_schema_file_valid():
    import json
    schema_path = Path("schemas/ingredients.schema.json")
    assert schema_path.exists()
    with schema_path.open("r", encoding="utf-8") as f:
        schema = json.load(f)
    assert "$defs" in schema
    assert "Ingredient" in schema["$defs"]
    assert "MacrosInfo" in schema["$defs"]
    assert "calories_kcal" in schema["$defs"]["MacrosInfo"]["properties"]
    assert "protein_g" in schema["$defs"]["MacrosInfo"]["properties"]
    assert "sodium_mg" in schema["$defs"]["MacrosInfo"]["properties"]



def test_all_ingredient_yaml_files_exist_and_validate_against_schema():
    schema_path = Path("schemas/ingredients.schema.json")
    assert schema_path.exists(), f"Schema not found: {schema_path}"
    with schema_path.open("r", encoding="utf-8") as f:
        schema = json.load(f)

    ingredients_dir = Path("data/ingredients")
    yaml_files = sorted(ingredients_dir.glob("*.yaml"))
    assert len(yaml_files) > 0, "No ingredient YAML files found in data/ingredients!"

    aisles_config = load_aisles(Path("data/aisles.yaml"))
    valid_aisle_ids = {a.id for a in aisles_config.aisles}

    units_reg = load_units(Path("data/units.yaml"))
    valid_containers = set(units_reg.schema_data.packaging_containers)

    seen_ids = set()

    for yaml_file in yaml_files:
        with yaml_file.open("r", encoding="utf-8") as f:
            raw_data = yaml.safe_load(f)

        assert isinstance(raw_data, list), f"{yaml_file.name} must contain a list of ingredients"
        assert len(raw_data) > 0, f"{yaml_file.name} is empty"

        # 1. Validate raw data structure against JSON Schema
        jsonschema.validate(instance=raw_data, schema=schema)

        # 2. Validate using Pydantic domain models
        ingredients = load_ingredients_file(yaml_file)
        assert len(ingredients) == len(raw_data)

        for item in ingredients:
            # Check ID uniqueness across all files
            assert item.id not in seen_ids, f"Duplicate ingredient ID '{item.id}' found in {yaml_file.name}"
            seen_ids.add(item.id)

            # Check aisle matches filename stem and aisles.yaml
            assert item.aisle == yaml_file.stem, (
                f"Ingredient '{item.id}' aisle '{item.aisle}' does not match file stem '{yaml_file.stem}'"
            )
            assert item.aisle in valid_aisle_ids, (
                f"Ingredient '{item.id}' aisle '{item.aisle}' not in valid aisles: {valid_aisle_ids}"
            )

            # Check package container is registered in units.yaml
            assert item.package.container in valid_containers, (
                f"Ingredient '{item.id}' container '{item.package.container}' not in units.yaml packaging_containers: {valid_containers}"
            )

            # Check computed prices
            assert item.price_per_100g > 0
            assert item.price_per_kg > 0
            assert item.price_per_unit > 0

            # Check conversions
            assert len(item.conversions) >= 1
            for conv in item.conversions:
                assert conv.g > 0



def test_schema_rejects_invalid_yaml():
    schema_path = Path("schemas/ingredients.schema.json")
    with schema_path.open("r", encoding="utf-8") as f:
        schema = json.load(f)

    # Missing mandatory 'shelf_life_days'
    invalid_data = [
        {
            "id": "bad-chicken",
            "name": "Bad Chicken",
            "aisle": "meat",
            "storage": "refrigerated",
            "package": {
                "container": "pack",
                "unit": "piece",
                "amount": 1,
                "container_weight_g": 500,
            },
            "reference": {
                "brand": "Test",
                "product": "Test",
                "price": 10.0,
            },
            "macros_per_100g": {
                "calories_kcal": 100,
                "protein_g": 20,
                "fat_g": 2,
                "carbs_g": 0,
                "fiber_g": 0,
            },
            "conversions": [{"unit": "piece", "g": 500}],
        }
    ]

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid_data, schema=schema)

