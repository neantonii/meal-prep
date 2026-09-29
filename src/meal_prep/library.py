"""Meal Prep Library Loader & Gateway.

Loads and validates all domain standards, ingredient catalogs, and recipes in a
single call. Ingredients are enriched (resolved into frozen values) via the
ingredient service; recipes remain authored documents until a later service
prepares them.
"""

from dataclasses import dataclass
from pathlib import Path
from meal_prep.dtos.units import UnitsFileSchema
from meal_prep.dtos.equipment import EquipmentItem
from meal_prep.dtos.aisle import Aisle
from meal_prep.models.ingredient import Ingredient
from meal_prep.dtos.recipe import Recipe
from meal_prep.adapters.units import load_units
from meal_prep.adapters.equipment import load_equipment
from meal_prep.adapters.aisles import load_aisles
from meal_prep.adapters.ingredients import load_all_ingredients
from meal_prep.adapters.recipes import load_all_recipes
from meal_prep.services.ingredients import prepare_catalog


@dataclass
class MealPrepLibrary:
    """Unified repository container with validated domain standards, ingredients, and recipes."""
    units: UnitsFileSchema
    equipment: list[EquipmentItem]
    aisles: list[Aisle]
    catalog: dict[str, Ingredient]
    recipes: dict[str, Recipe]

    @classmethod
    def load(
        cls,
        data_dir: Path | str = Path("data"),
        recipes_dir: Path | str = Path("recipes"),
    ) -> "MealPrepLibrary":
        """Load and validate the entire meal prep workspace in a single line.

        Args:
            data_dir: Directory containing taxonomy YAMLs (units.yaml, equipment.yaml, aisles.yaml, ingredients/).
            recipes_dir: Directory containing .cook recipe files.

        Returns:
            Fully initialized, cross-validated MealPrepLibrary instance.
        """
        data_path = Path(data_dir)
        recipes_path = Path(recipes_dir)

        units = load_units(data_path / "units.yaml")
        equipment = load_equipment(data_path / "equipment.yaml")
        aisles = load_aisles(data_path / "aisles.yaml")
        catalog = prepare_catalog(
            load_all_ingredients(data_path / "ingredients"),
            units,
            {aisle.id: aisle for aisle in aisles},
        )

        recipes: dict[str, Recipe] = {}
        if recipes_path.exists():
            recipes = load_all_recipes(recipes_dir=recipes_path)

        return cls(
            units=units,
            equipment=equipment,
            aisles=aisles,
            catalog=catalog,
            recipes=recipes,
        )
