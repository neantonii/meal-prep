import pytest
from pydantic import BaseModel, ValidationError
from meal_prep.models.enums import StorageType, RecipeCategory


class DummyItem(BaseModel):
    storage: StorageType
    category: RecipeCategory


def test_storage_type_values_and_display():
    assert StorageType.AMBIENT == "ambient"
    assert StorageType.REFRIGERATED == "refrigerated"
    assert StorageType.FROZEN == "frozen"

    assert StorageType.AMBIENT.display_name == "Pantry (Ambient)"
    assert StorageType.REFRIGERATED.display_name == "Refrigerated (Chilled)"
    assert StorageType.FROZEN.display_name == "Frozen"


def test_recipe_category_values_and_display():
    assert RecipeCategory.MODULAR_PROTEIN == "modular_protein"
    assert RecipeCategory.MODULAR_PROTEIN.display_name == "Modular Protein"
    assert "High-protein" in RecipeCategory.MODULAR_PROTEIN.description

    assert RecipeCategory.BREAKFAST == "breakfast"
    assert RecipeCategory.BREAKFAST.display_name == "Breakfast"


def test_pydantic_validation_success():
    item = DummyItem(storage="frozen", category="modular_protein")
    assert item.storage == StorageType.FROZEN
    assert item.category == RecipeCategory.MODULAR_PROTEIN


def test_pydantic_validation_failure():
    with pytest.raises(ValidationError):
        DummyItem(storage="in_the_sun", category="modular_protein")

    with pytest.raises(ValidationError):
        DummyItem(storage="frozen", category="dessert")
