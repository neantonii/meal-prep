from pathlib import Path
from typing import Any, TYPE_CHECKING
import yaml
from pydantic import BaseModel, Field, PrivateAttr, field_validator, model_validator
from meal_prep.models.enums import StorageType

if TYPE_CHECKING:
    from meal_prep.models.units import UnitsRegistry
    from meal_prep.models.conversion_graph import ConversionGraph


class PackageInfo(BaseModel):
    container: str = Field(..., description="Container noun, e.g. pack, bag, carton, bottle, loaf")
    unit: str = Field(..., description="Unit noun of items in container, e.g. piece, slice, item, g, ml")
    amount: float = Field(..., gt=0, description="Amount of units in the container")
    container_weight_g: float = Field(..., gt=0, description="Total container net weight in grams")

    @field_validator("container", "unit")
    @classmethod
    def clean_strings(cls, v: str) -> str:
        clean = v.strip().lower()
        if not clean:
            raise ValueError("Field cannot be empty")
        return clean


class ReferenceInfo(BaseModel):
    brand: str = Field(..., description="Brand name, e.g. Compliments")
    product: str = Field(..., description="Full commercial product name")
    price: float = Field(..., gt=0, description="Retail purchase price in CAD")


class MacrosInfo(BaseModel):
    calories_kcal: float = Field(..., ge=0, description="Calories (kcal) per 100g")
    protein_g: float = Field(..., ge=0, description="Protein in grams per 100g")
    fat_g: float = Field(..., ge=0, description="Total fat in grams per 100g")
    carbs_g: float = Field(..., ge=0, description="Total carbohydrates in grams per 100g")
    fiber_g: float = Field(..., ge=0, description="Dietary fiber in grams per 100g")

    # Optional detailed nutrients
    saturated_fat_g: float | None = Field(None, ge=0, description="Saturated fat in grams per 100g")
    sugars_g: float | None = Field(None, ge=0, description="Total sugars in grams per 100g")
    sodium_mg: float | None = Field(None, ge=0, description="Sodium in milligrams per 100g")
    potassium_mg: float | None = Field(None, ge=0, description="Potassium in milligrams per 100g")


class UnitConversion(BaseModel):
    unit: str = Field(..., description="Measurement unit name, e.g. piece, cup, tbsp")
    g: float = Field(..., gt=0, description="Mass equivalent in grams")

    @field_validator("unit")
    @classmethod
    def validate_unit(cls, v: str) -> str:
        clean = v.strip().lower()
        if not clean:
            raise ValueError("Unit cannot be empty")
        return clean


class Ingredient(BaseModel):
    id: str = Field(..., description="Canonical unique slug, e.g. 'boneless-chicken-breast'")
    name: str = Field(..., description="Generic staple display name")
    aisle: str = Field(..., description="Supermarket aisle slug")
    storage: StorageType = Field(..., description="Storage temperature classification")
    shelf_life_days: int = Field(..., gt=0, description="Mandatory shelf life in days under this storage mode")

    package: PackageInfo
    reference: ReferenceInfo
    macros_per_100g: MacrosInfo
    conversions: list[UnitConversion] = Field(..., min_length=1, description="Mandatory list of unit-to-gram conversions")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        clean = v.strip().lower()
        if not clean:
            raise ValueError("Ingredient id cannot be empty")
        if not clean.replace("-", "").isalnum():
            raise ValueError(f"Ingredient id '{v}' must be alphanumeric with hyphens")
        return clean

    _conversion_graph: Any = PrivateAttr(default=None)

    @property
    def price_per_100g(self) -> float:
        """Calculated retail unit price per 100g in CAD."""
        return round((self.reference.price / self.package.container_weight_g) * 100, 2)

    @property
    def price_per_kg(self) -> float:
        """Calculated retail unit price per kg in CAD."""
        return round(self.price_per_100g * 10, 2)

    @property
    def price_per_unit(self) -> float:
        """Calculated price per individual package unit (e.g. per piece, slice, egg, ml, or g)."""
        return round(self.reference.price / self.package.amount, 4)

    def get_conversion_factor(self, unit_name: str) -> float | None:
        """Returns the mass in grams for 1 unit of unit_name, or None."""
        clean = unit_name.strip().lower()
        for conv in self.conversions:
            if conv.unit == clean:
                return conv.g
        return None

    def get_conversion_graph(self, units: "UnitsRegistry") -> "ConversionGraph":
        """Returns the precomputed conversion graph, building and caching it if not already done."""
        if self._conversion_graph is None:
            from meal_prep.models.conversion_graph import build_conversion_graph
            self._conversion_graph = build_conversion_graph(self, units)
        return self._conversion_graph

    def convert(self, amount: float, from_unit: str, to_unit: str, units: "UnitsRegistry") -> float:
        """Convert amount from from_unit to to_unit for this ingredient."""
        return self.get_conversion_graph(units).convert(amount, from_unit, to_unit)


def load_ingredients_file(path: Path | str) -> list[Ingredient]:
    """Load and validate all ingredients from an aisle YAML file."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Ingredients file not found at: {file_path}")

    with file_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

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


def load_all_ingredients(
    dir_path: Path | str = Path("data/ingredients"),
    units: "UnitsRegistry | None" = None,
) -> dict[str, Ingredient]:
    """Load all ingredients across all aisle YAML files and ensure global ID uniqueness.
    
    If units is provided, precomputes and caches the conversion graph for all ingredients at load time.
    """
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
            if units is not None:
                item.get_conversion_graph(units)
            all_ingredients[item.id] = item

    return all_ingredients
