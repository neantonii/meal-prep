"""Pinned domain vocabulary (``enums.py``).

Each enum is a closed taxonomy: adding a member is a deliberate product
decision (new supermarket aisle, new storage mode, ...), never a side
effect of authoring data. These tests fail loudly on any expansion so the
new member gets explicit review instead of slipping in silently.
"""

from __future__ import annotations

from meal_prep.enums import Aisle, Mealtime, RecipeCategory, StorageType


def test_aisle_vocabulary_is_pinned():
    assert set(Aisle) == {
        Aisle.PRODUCE,
        Aisle.MEAT,
        Aisle.SEAFOOD,
        Aisle.DAIRY,
        Aisle.PANTRY,
        Aisle.SPICES,
    }, (
        "Aisle vocabulary changed. Adding an aisle is a product decision, "
        "not an authoring side effect: confirm the new aisle with the user, "
        "add its data/ingredients/<aisle>.yaml file, and update this pin."
    )


def test_storage_type_vocabulary_is_pinned():
    assert set(StorageType) == {
        StorageType.AMBIENT,
        StorageType.REFRIGERATED,
        StorageType.FROZEN,
    }, (
        "StorageType vocabulary changed. Adding a storage mode is a product "
        "decision, not an authoring side effect: confirm it with the user "
        "and update this pin."
    )


def test_mealtime_vocabulary_is_pinned():
    assert set(Mealtime) == {
        Mealtime.BREAKFAST,
        Mealtime.LUNCH,
        Mealtime.DINNER,
        Mealtime.SNACKS,
    }, (
        "Mealtime vocabulary changed. Adding a mealtime is a product "
        "decision, not an authoring side effect: confirm it with the user "
        "and update this pin."
    )


def test_recipe_category_vocabulary_is_pinned():
    assert set(RecipeCategory) == {
        RecipeCategory.MODULAR_PROTEIN,
        RecipeCategory.MODULAR_CARB,
        RecipeCategory.MODULAR_COOKED_VEG,
        RecipeCategory.FRESH_SALAD_VEG,
        RecipeCategory.BREAKFAST,
        RecipeCategory.SNACKS,
    }, (
        "RecipeCategory vocabulary changed. Adding a category is a product "
        "decision, not an authoring side effect: confirm it with the user "
        "and update this pin."
    )
