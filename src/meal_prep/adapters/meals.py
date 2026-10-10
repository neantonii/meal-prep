"""YAML adapter for authored meals (``meals/<slug>.yaml``)."""

from pathlib import Path

from meal_prep.adapters._yaml import read_yaml
from meal_prep.dtos.meal import MealDTO


def load_meal_file(path: Path | str) -> MealDTO:
    """Load and validate one authored meal file into its DTO.

    Performs only deserialization and shape validation (mapping shape, slug
    formats, ID/file-layout consistency). Cross-validation against prepared
    recipes is enrichment and lives in a service.
    """
    file_path = Path(path)
    data = read_yaml(file_path, what="Meal")

    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML structure in {file_path}: expected a mapping")

    meal = MealDTO.model_validate(data)

    if meal.id != file_path.stem:
        raise ValueError(
            f"Meal ID '{meal.id}' does not match filename stem "
            f"'{file_path.stem}' in {file_path}"
        )
    meal.source_path = file_path
    return meal


def load_all_meals(meals_dir: Path | str = Path("meals")) -> dict[str, MealDTO]:
    """Load and validate all authored meal files and ensure ID uniqueness."""
    directory = Path(meals_dir)
    if not directory.exists() or not directory.is_dir():
        raise FileNotFoundError(f"Meals directory not found: {directory}")

    meals: dict[str, MealDTO] = {}
    for yaml_file in sorted(directory.rglob("*.yaml")):
        meal = load_meal_file(yaml_file)
        if meal.id in meals:
            raise ValueError(
                f"Duplicate meal ID '{meal.id}' found across multiple files!"
            )
        meals[meal.id] = meal

    return meals
