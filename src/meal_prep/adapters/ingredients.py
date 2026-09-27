"""YAML adapter for the ingredient catalog (``data/ingredients/<aisle>.yaml``)."""

from pathlib import Path

from meal_prep.adapters._yaml import read_yaml
from meal_prep.models.ingredient import Ingredient
from meal_prep.models.units import UnitsRegistry
from meal_prep.services.pricing import container_weight_g
from meal_prep.services.validation import validate_conversions


def load_ingredients_file(path: Path | str, units: UnitsRegistry | None = None) -> list[Ingredient]:
    """Load and validate all ingredients from an aisle YAML file.

    When ``units`` is provided, runs the collaborative conversion cross-checks
    (which need the registry) for each ingredient.
    """
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
        if units is not None:
            validate_conversions(ingredient, units)
        ingredients.append(ingredient)

    return ingredients


def load_all_ingredients(
    dir_path: Path | str = Path("data/ingredients"),
    units: UnitsRegistry | None = None,
) -> dict[str, Ingredient]:
    """Load all ingredients across all aisle YAML files and ensure global ID uniqueness.

    If units is provided, precomputes and caches the conversion graph for all ingredients at load time.
    """
    directory = Path(dir_path)
    if not directory.exists() or not directory.is_dir():
        raise FileNotFoundError(f"Ingredients directory not found: {directory}")

    all_ingredients: dict[str, Ingredient] = {}
    for yaml_file in sorted(directory.glob("*.yaml")):
        items = load_ingredients_file(yaml_file, units=units)
        for item in items:
            if item.id in all_ingredients:
                raise ValueError(
                    f"Duplicate ingredient ID '{item.id}' found across multiple files! "
                    f"Already loaded from {all_ingredients[item.id].aisle}.yaml, duplicate in {yaml_file.name}"
                )
            if units is not None:
                item.get_conversion_graph(units)  # build + validate; caches on the ingredient
                if container_weight_g(item, units) <= 0:
                    raise ValueError(
                        f"Ingredient '{item.id}' package container '{item.package.container}' cannot "
                        f"be resolved to grams, so its net weight is not derivable. Bridge the "
                        f"package unit '{item.package.unit}' to a mass unit."
                    )
            all_ingredients[item.id] = item

    return all_ingredients
