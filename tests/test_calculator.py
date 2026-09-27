from pathlib import Path
import pytest
from meal_prep.adapters.units import load_units
from meal_prep.adapters.equipment import load_equipment
from meal_prep.adapters.ingredients import load_all_ingredients
from meal_prep.adapters.recipes import load_recipe_file
from meal_prep.calculator import prepare_recipe, PreparedRecipe, IngredientBreakdown


@pytest.fixture
def test_setup():
    units = load_units(Path("data/units.yaml"))
    equipment = load_equipment(Path("data/equipment.yaml"))
    catalog = load_all_ingredients(Path("data/ingredients"), units=units)
    recipe = load_recipe_file(
        Path("recipes/modular_protein/air-fried-chicken-breast.cook"),
        catalog=catalog,
        equipment_reg=equipment,
        units_reg=units,
    )
    return units, equipment, catalog, recipe


def test_prepare_recipe_computations(test_setup):
    units, equipment, catalog, recipe = test_setup

    prepared = prepare_recipe(recipe, catalog, units, equipment)
    assert isinstance(prepared, PreparedRecipe)

    # Basic metadata
    assert prepared.id == "air-fried-chicken-breast"
    assert prepared.title == "Air-Fried Seasoned Chicken Breast"
    assert prepared.category == "modular_protein"
    assert prepared.servings == 4

    # Weights
    assert prepared.cooked_batch_weight_g == 660.0
    assert prepared.portion_cooked_weight_g == 165.0
    assert prepared.raw_batch_weight_g == pytest.approx(975.3, abs=0.5)
    assert prepared.cooking_loss_percent == pytest.approx(32.3, abs=0.5)

    # Costs
    assert prepared.batch_cost > 20.0
    assert prepared.serving_cost == pytest.approx(prepared.batch_cost / 4, abs=0.01)

    # Macros
    assert prepared.batch_macros.calories_kcal == pytest.approx(1186.6, abs=1.0)
    assert prepared.batch_macros.protein_g == pytest.approx(219.2, abs=1.0)
    assert prepared.serving_macros.calories_kcal == pytest.approx(296.6, abs=1.0)
    assert prepared.serving_macros.protein_g == pytest.approx(54.8, abs=0.5)

    # Storage constraint
    assert prepared.safe_fridge_days == 3
    assert prepared.freezer_friendly is True

    # Ingredient breakdown detail
    assert len(prepared.ingredients) == len(recipe.ingredients)
    chicken_breakdown = next(item for item in prepared.ingredients if item.id == "boneless-chicken-breast")
    assert chicken_breakdown.name == "Boneless, Skinless Chicken Breast"
    assert chicken_breakdown.grams == 950.0
    assert chicken_breakdown.cost > 20.0
    assert "950.0g" in chicken_breakdown.detail_text


def test_review_math_output(test_setup):
    units, equipment, catalog, recipe = test_setup

    prepared = prepare_recipe(recipe, catalog, units, equipment)
    audit = prepared.review_math()

    assert "MATH AUDIT: Air-Fried Seasoned Chicken Breast" in audit
    assert "Yield: 4 servings" in audit
    assert "INGREDIENT CONTRIBUTIONS:" in audit
    assert "Boneless, Skinless Chicken Breast" in audit
    assert "BATCH TOTALS:" in audit
    assert "PER PORTION (/ 4):" in audit
