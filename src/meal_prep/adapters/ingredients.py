"""YAML adapter for the ingredient catalog (``data/ingredients/<aisle>.yaml``)."""

from pathlib import Path

from meal_prep.adapters._yaml import read_yaml
from meal_prep.models.ingredient import Ingredient


def load_ingredients_file(path: Path | str) -> list[Ingredient]:
    """Load and validate all ingredients from an aisle YAML file."""
    file_path = Path(path)
    data = read_yaml(file_path, what="Ingredients")

    if not isinstance(data, list):
        raise ValueError(f"Invalid YAML structure in {file_path}: expected a list of ingredients")

    expected_aisle = file_path.stem
    ingredients = []
    for item_data in data:
        ingredient = Ingredient.model_validate(item_data)
        if ingredient.aisle != expected_aisle:
            raise ValueError(
                f"Ingredient '{ingredient.id}' declares aisle '{ingredient.aisle}', "
                f"which does not match file stem '{expected_aisle}' in {file_path}"
            )
        ingredients.append(ingredient)

    return ingredients


def load_all_ingredients(dir_path: Path | str = Path("data/ingredients")) -> dict[str, Ingredient]:
    """Load all ingredients across all aisle YAML files and ensure global ID uniqueness."""
    directory = Path(dir_path)
    if not directory.exists() or not directory.is_dir():
        raise FileNotFoundError(f"Ingredients directory not found: {directory}")

    all_ingredients: dict[str, Ingredient] = {}
    for yaml_file in sorted(directory.glob("*.yaml")):
        items = load_ingredients_file(yaml_file)
        for item in items:
            if item.id in all_ingredients:
                raise ValueError(
                    f"Duplicate ingredient ID '{item.id}' found across multiple files! "
                    f"Already loaded from {all_ingredients[item.id].aisle}.yaml, duplicate in {yaml_file.name}"
                )
            all_ingredients[item.id] = item

    return all_ingredients
