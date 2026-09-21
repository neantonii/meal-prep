from pathlib import Path
import pytest
from meal_prep.library import MealPrepLibrary
from meal_prep.calculator import PreparedRecipe


def test_library_loads_all_in_one_line():
    lib = MealPrepLibrary.load(
        data_dir=Path("data"),
        recipes_dir=Path("recipes"),
    )

    assert lib.units.is_valid_unit("g")
    assert len(lib.equipment.items) > 0
    assert len(lib.aisles.aisles) > 0
    assert len(lib.catalog) >= 21
    assert len(lib.recipes) >= 7

    # Can prepare a recipe directly
    prepared = lib.prepare("air-fried-chicken-breast")
    assert isinstance(prepared, PreparedRecipe)
    assert prepared.id == "air-fried-chicken-breast"

    # Can prepare all recipes
    all_prepared = lib.prepare_all()
    assert len(all_prepared) == len(lib.recipes)

    # Can review math in one call
    review = lib.review_math("air-fried-chicken-breast")
    assert "MATH AUDIT: Air-Fried Seasoned Chicken Breast" in review


def test_library_prepare_unknown_recipe_raises():
    lib = MealPrepLibrary.load(
        data_dir=Path("data"),
        recipes_dir=Path("recipes"),
    )
    with pytest.raises(KeyError, match="not found in loaded library"):
        lib.prepare("non-existent-recipe")
