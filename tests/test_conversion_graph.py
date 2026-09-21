from pathlib import Path
import pytest
from meal_prep.models.units import load_units
from meal_prep.models.ingredient import load_all_ingredients, Ingredient
from meal_prep.models.conversion_graph import build_conversion_graph


@pytest.fixture
def units():
    return load_units(Path("data/units.yaml"))


@pytest.fixture
def chicken(units):
    catalog = load_all_ingredients(Path("data/ingredients"), units=units)
    return catalog["boneless-chicken-breast"]


def test_chicken_breast_discrete_and_mass_conversions(chicken, units):
    graph = chicken.get_conversion_graph(units)

    # 1 piece = 237.5 g
    assert graph.convert(1, "piece", "g") == 237.5
    assert graph.convert(2, "piece", "g") == 475.0

    # 1 piece to kg (transitive: piece -> g -> kg)
    assert graph.convert(1, "piece", "kg") == 0.2375

    # Reverse: 475 g to pieces
    assert graph.convert(475, "g", "piece") == 2.0


def test_chicken_breast_packaging_conversions(chicken, units):
    graph = chicken.get_conversion_graph(units)

    # 1 pack = 4 pieces
    assert graph.convert(1, "pack", "piece") == 4.0
    assert graph.convert(4, "piece", "pack") == 1.0

    # 1 pack = 950 g
    assert graph.convert(1, "pack", "g") == 950.0
    assert graph.convert(950, "g", "pack") == 1.0
    assert graph.convert(1900, "g", "pack") == 2.0

    # 1 pack to kg
    assert graph.convert(1, "pack", "kg") == 0.95


def test_unreachable_conversion_raises_error(chicken, units):
    graph = chicken.get_conversion_graph(units)

    # Chicken has no volume/density bridge
    assert graph.can_convert("cup", "g") is False
    assert graph.can_convert("piece", "tbsp") is False

    with pytest.raises(ValueError, match="No conversion path exists"):
        graph.convert(1, "cup", "g")

    with pytest.raises(ValueError, match="No conversion path exists"):
        chicken.convert(2, "cup", "piece", units=units)


def test_alias_and_plural_normalization(chicken, units):
    # Testing alias "pieces" -> "piece", "grams" -> "g", "packs" -> "pack"
    assert chicken.convert(2, "pieces", "grams", units=units) == 475.0
    assert chicken.convert(1, "packs", "pieces", units=units) == 4.0


def test_ingredient_with_density_bridge(units):
    """Test ingredient that defines a volume-to-mass bridge (e.g. olive oil: 1 ml = 0.92 g)."""
    olive_oil = Ingredient.model_validate(
        {
            "id": "extra-virgin-olive-oil",
            "name": "Extra Virgin Olive Oil",
            "aisle": "pantry",
            "storage": "ambient",
            "shelf_life_days": 365,
            "package": {
                "container": "bottle",
                "unit": "ml",
                "amount": 1000,
                "container_weight_g": 920,
            },
            "reference": {
                "brand": "Compliments",
                "product": "Extra Virgin Olive Oil 1L",
                "price": 14.99,
            },
            "macros_per_100g": {
                "calories_kcal": 884.0,
                "protein_g": 0.0,
                "fat_g": 100.0,
                "carbs_g": 0.0,
                "fiber_g": 0.0,
            },
            "conversions": [
                {"from": "ml", "to": "g", "factor": 0.92},  # Density bridge!
            ],
        }
    )

    graph = olive_oil.get_conversion_graph(units)

    # Volume can now convert to mass!
    assert graph.can_convert("tbsp", "g") is True
    assert graph.can_convert("cup", "g") is True

    # 1 tbsp = 15 ml * 0.92 g/ml = 13.8 g
    assert graph.convert(1, "tbsp", "g") == 13.8

    # 1 cup = 240 ml * 0.92 g/ml = 220.8 g
    assert graph.convert(1, "cup", "g") == 220.8

    # 1 bottle = 1000 ml = 920 g
    assert graph.convert(1, "bottle", "ml") == 1000.0
    assert graph.convert(1, "bottle", "g") == 920.0

def test_conversion_for_tsp_works_with_only_tbsp_supplied(units):
    """Test that an ingredient with only tbsp supplied can convert tsp via standard intermediate units."""
    butter = Ingredient.model_validate(
        {
            "id": "unsalted-butter",
            "name": "Unsalted Butter",
            "aisle": "dairy",
            "storage": "refrigerated",
            "shelf_life_days": 90,
            "package": {
                "container": "pack",
                "unit": "g",
                "amount": 454,
                "container_weight_g": 454,
            },
            "reference": {
                "brand": "Compliments",
                "product": "Compliments Butter Unsalted 454 g",
                "price": 6.69,
            },
            "macros_per_100g": {
                "calories_kcal": 700.0,
                "protein_g": 1.0,
                "fat_g": 80.0,
                "carbs_g": 0.0,
                "fiber_g": 0.0,
            },
            "conversions": [
                {"from": "tbsp", "to": "g", "factor": 14.2},
            ],
        }
    )

    graph = butter.get_conversion_graph(units)

    # Invariant units: 1 tbsp = 15 ml, 1 tsp = 5 ml -> 1 tbsp = 3 tsp
    assert graph.can_convert("tsp", "g") is True
    assert graph.can_convert("tbsp", "g") is True

    # 1 tbsp = 14.2 g
    assert graph.convert(1, "tbsp", "g") == 14.2
    # 1 tsp = 14.2 / 3 = 4.733333 g
    assert graph.convert(1, "tsp", "g") == pytest.approx(14.2 / 3.0, rel=1e-4)
    # 3 tsp = 14.2 g
    assert graph.convert(3, "tsp", "g") == pytest.approx(14.2, rel=1e-4)
    # Reverse conversion: 14.2 g to tsp = 3 tsp
    assert graph.convert(14.2, "g", "tsp") == pytest.approx(3.0, rel=1e-4)


def test_arbitrary_edges_and_reverse_transformations(units):
    """Test arbitrary edge between discrete unit and volume, and automatic reverse transformation."""
    protein_powder = Ingredient.model_validate(
        {
            "id": "whey-protein",
            "name": "Whey Protein Powder",
            "aisle": "pantry",
            "storage": "ambient",
            "shelf_life_days": 365,
            "package": {
                "container": "tub",
                "unit": "scoop",
                "amount": 30,
                "container_weight_g": 900,
            },
            "reference": {
                "brand": "Optimum Nutrition",
                "product": "Gold Standard 100% Whey 900g",
                "price": 45.99,
            },
            "macros_per_100g": {
                "calories_kcal": 400.0,
                "protein_g": 80.0,
                "fat_g": 5.0,
                "carbs_g": 10.0,
                "fiber_g": 0.0,
            },
            "conversions": [
                # Arbitrary edge: 1 scoop = 2 tbsp (discrete count to volume, no grams directly)
                {"from": "scoop", "to": "tbsp", "factor": 2.0},
            ],
        }
    )

    graph = protein_powder.get_conversion_graph(units)

    # 1 scoop = 2 tbsp
    assert graph.convert(1, "scoop", "tbsp") == 2.0
    # Automatic reverse: 2 tbsp = 1 scoop (inverse coefficient 1/2)
    assert graph.convert(2, "tbsp", "scoop") == 1.0

    # Transitive via volume units: 1 tbsp = 15 ml, 1 tsp = 5 ml
    # 1 scoop = 2 tbsp = 30 ml
    assert graph.convert(1, "scoop", "ml") == 30.0
    assert graph.convert(30, "ml", "scoop") == 1.0

    # 1 scoop = 6 tsp
    assert graph.convert(1, "scoop", "tsp") == 6.0
    assert graph.convert(6, "tsp", "scoop") == 1.0
