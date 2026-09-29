"""Tests for the ingredient YAML adapter (``adapters/ingredients.py``).

Happy paths plus the adapter's own structure/consistency errors: non-list root,
aisle/stem mismatch, missing directory, and duplicate ID across files. Per-item
shape validation belongs to ``IngredientDTO`` and is not re-tested.
"""

from __future__ import annotations

import pytest

from meal_prep.adapters.ingredients import load_all_ingredients, load_ingredients_file
from meal_prep.dtos.ingredient import IngredientDTO


def _ingredient_yaml(aisle: str = "dairy", id_: str = "unsalted-butter"):
    return (
        f"- id: {id_}\n"
        f"  name: Test\n"
        f"  step_name: test\n"
        f"  aisle: {aisle}\n"
        "  storage: refrigerated\n"
        "  shelf_life_days: 90\n"
        "  reference:\n    brand: b\n    product: p\n    price: 5.0\n"
        "  macros:\n    unit: g\n    amount: 100\n    calories_kcal: 100\n"
        "    protein_g: 1\n    fat_g: 1\n    carbs_g: 1\n    fiber_g: 0\n"
        "  conversions:\n    - from: package\n      to: g\n      factor: 454\n"
    )


# ---------------------------------------------------------------------------
# load_ingredients_file — happy paths
# ---------------------------------------------------------------------------


def test_load_ingredients_file_valid(tmp_path):
    path = tmp_path / "dairy.yaml"
    path.write_text(_ingredient_yaml(), encoding="utf-8")
    items = load_ingredients_file(path)
    assert len(items) == 1
    assert isinstance(items[0], IngredientDTO)
    assert items[0].id == "unsalted-butter"
    assert items[0].aisle == "dairy"


# ---------------------------------------------------------------------------
# load_ingredients_file — structure errors
# ---------------------------------------------------------------------------


def test_load_ingredients_file_rejects_non_list_root(tmp_path):
    path = tmp_path / "dairy.yaml"
    path.write_text("id: x\n", encoding="utf-8")
    with pytest.raises(ValueError, match="expected a list of ingredients"):
        load_ingredients_file(path)


def test_load_ingredients_file_rejects_aisle_stem_mismatch(tmp_path):
    path = tmp_path / "dairy.yaml"
    path.write_text(_ingredient_yaml(aisle="pantry"), encoding="utf-8")
    with pytest.raises(ValueError, match="does not match file stem 'dairy'"):
        load_ingredients_file(path)


# ---------------------------------------------------------------------------
# load_all_ingredients — happy paths
# ---------------------------------------------------------------------------


def test_load_all_ingredients_valid(tmp_path):
    (tmp_path / "dairy.yaml").write_text(
        _ingredient_yaml(aisle="dairy", id_="butter"), encoding="utf-8"
    )
    (tmp_path / "meat.yaml").write_text(
        _ingredient_yaml(aisle="meat", id_="chicken"), encoding="utf-8"
    )
    catalog = load_all_ingredients(tmp_path)
    assert set(catalog) == {"butter", "chicken"}


def test_load_all_ingredients_ignores_non_yaml(tmp_path):
    (tmp_path / "dairy.yaml").write_text(
        _ingredient_yaml(aisle="dairy", id_="butter"), encoding="utf-8"
    )
    (tmp_path / "notes.txt").write_text("ignore me", encoding="utf-8")
    catalog = load_all_ingredients(tmp_path)
    assert set(catalog) == {"butter"}


# ---------------------------------------------------------------------------
# load_all_ingredients — errors
# ---------------------------------------------------------------------------


def test_load_all_ingredients_missing_directory():
    with pytest.raises(FileNotFoundError, match="Ingredients directory not found"):
        load_all_ingredients("/nonexistent/ingredients")


def test_load_all_ingredients_rejects_duplicate_id_across_files(tmp_path):
    (tmp_path / "dairy.yaml").write_text(
        _ingredient_yaml(aisle="dairy", id_="butter"), encoding="utf-8"
    )
    (tmp_path / "pantry.yaml").write_text(
        _ingredient_yaml(aisle="pantry", id_="butter"), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="Duplicate ingredient ID 'butter'"):
        load_all_ingredients(tmp_path)
