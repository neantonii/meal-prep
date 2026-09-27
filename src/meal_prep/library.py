"""Meal Prep Library Loader & Gateway.

Loads, validates, and links all domain standards, ingredient catalogs, and recipes in a single call.
Provides direct access to prepared mathematical data without invoking HTML renderers.
"""

from dataclasses import dataclass
from pathlib import Path
from meal_prep.models.units import UnitsRegistry
from meal_prep.models.equipment import EquipmentRegistry
from meal_prep.models.aisle import AislesConfig
from meal_prep.models.ingredient import Ingredient
from meal_prep.models.recipe import Recipe
from meal_prep.adapters.units import load_units
from meal_prep.adapters.equipment import load_equipment
from meal_prep.adapters.aisles import load_aisles
from meal_prep.adapters.ingredients import load_all_ingredients
from meal_prep.adapters.recipes import load_all_recipes
from meal_prep.calculator import PreparedRecipe, prepare_recipe


@dataclass
class MealPrepLibrary:
    """Unified repository container with validated domain standards, ingredients, and recipes."""
    units: UnitsRegistry
    equipment: EquipmentRegistry
    aisles: AislesConfig
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
        catalog = load_all_ingredients(data_path / "ingredients", units=units)

        recipes: dict[str, Recipe] = {}
        if recipes_path.exists():
            recipes = load_all_recipes(
                recipes_dir=recipes_path,
                catalog=catalog,
                units_reg=units,
                equipment_reg=equipment,
            )

        return cls(
            units=units,
            equipment=equipment,
            aisles=aisles,
            catalog=catalog,
            recipes=recipes,
        )

    def prepare(self, recipe_id: str) -> PreparedRecipe:
        """Compute all mathematical and nutritional data for a specific recipe."""
        if recipe_id not in self.recipes:
            raise KeyError(f"Recipe '{recipe_id}' not found in loaded library. Available: {list(self.recipes.keys())}")
        return prepare_recipe(
            recipe=self.recipes[recipe_id],
            catalog=self.catalog,
            units=self.units,
            equipment=self.equipment,
        )

    def prepare_all(self) -> dict[str, PreparedRecipe]:
        """Compute all mathematical and nutritional data for all recipes in the library."""
        return {
            rid: self.prepare(rid)
            for rid in self.recipes
        }

    def review_math(self, recipe_id: str) -> str:
        """Return a formatted audit of the calculations for a specific recipe."""
        return self.prepare(recipe_id).review_math()
