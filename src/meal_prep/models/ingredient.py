from pathlib import Path
from typing import Any, TYPE_CHECKING
import yaml
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator, model_validator
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
    model_config = ConfigDict(populate_by_name=True)

    from_unit: str = Field(..., alias="from", description="Source measurement unit")
    to_unit: str = Field(..., alias="to", description="Target measurement unit")
    factor: float = Field(..., gt=0, description="Multiplier such that 1 from_unit = factor * to_unit")

    @field_validator("from_unit", "to_unit")
    @classmethod
    def clean_units(cls, v: str) -> str:
        clean = v.strip().lower()
        if not clean:
            raise ValueError("Unit cannot be empty")
        return clean

    @model_validator(mode="after")
    def validate_different_units(self) -> "UnitConversion":
        if self.from_unit == self.to_unit:
            raise ValueError(f"Conversion from unit '{self.from_unit}' to itself is redundant.")
        return self


class Ingredient(BaseModel):
    id: str = Field(..., description="Canonical unique slug, e.g. 'boneless-chicken-breast'")
    name: str = Field(..., description="Generic staple display name")
    aisle: str = Field(..., description="Supermarket aisle slug")
    storage: StorageType = Field(..., description="Storage temperature classification")
    shelf_life_days: int = Field(..., gt=0, description="Mandatory shelf life in days under this storage mode")

    package: PackageInfo
    reference: ReferenceInfo
    macros_per_100g: MacrosInfo
    conversions: list[UnitConversion] = Field(..., min_length=1, description="Mandatory list of unit conversions")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        clean = v.strip().lower()
        if not clean:
            raise ValueError("Ingredient id cannot be empty")
        if not clean.replace("-", "").isalnum():
            raise ValueError(f"Ingredient id '{v}' must be alphanumeric with hyphens")
        return clean

    @model_validator(mode="after")
    def validate_conversions_uniqueness_and_dimensions(self) -> "Ingredient":
        """Ensure no double conversions across any pair of dimensions (including flipped directions).

        Rules:
        1. No duplicate edges (e.g. defining A -> B twice, or defining both A -> B and B -> A).
        2. No intra-dimension conversions for dimensions that already have universal conversions
           (e.g. volume -> volume like tbsp -> tsp, or mass -> mass like kg -> g).
        3. No double conversion across the same pair of dimensions (e.g. defining both tbsp -> g
           and tsp -> g, or defining ml -> g and g -> tbsp).
        """
        from meal_prep.models.units import get_default_units
        try:
            units_reg = get_default_units()
        except Exception:
            return self

        def get_dim_key(unit_name: str) -> str | tuple[str, str]:
            clean = unit_name.strip().lower()
            if units_reg.is_valid_unit(clean):
                canonical = units_reg.normalize(clean)
                dim = units_reg.dimension_of(canonical)
                group = getattr(units_reg.schema_data, dim, None)
                if group and group.conversions:
                    # Continuous physical dimension with universal intermediate conversions (e.g. mass, volume, time)
                    return dim
                return (dim, canonical)
            return ("discrete", clean)

        def format_dim(dim_key: str | tuple[str, str]) -> str:
            if isinstance(dim_key, tuple):
                return f"{dim_key[0]}:{dim_key[1]}"
            return dim_key

        seen_edges: set[frozenset[str]] = set()
        seen_dim_pairs: set[frozenset[str | tuple[str, str]]] = set()

        for conv in self.conversions:
            u_from = conv.from_unit.strip().lower()
            if units_reg.is_valid_unit(u_from):
                u_from = units_reg.normalize(u_from)

            u_to = conv.to_unit.strip().lower()
            if units_reg.is_valid_unit(u_to):
                u_to = units_reg.normalize(u_to)

            # 1. Check duplicate edge (A -> B or B -> A)
            edge_key = frozenset([u_from, u_to])
            if edge_key in seen_edges:
                raise ValueError(
                    f"Duplicate conversion between '{conv.from_unit}' and '{conv.to_unit}' "
                    f"defined in ingredient '{self.id}'."
                )
            seen_edges.add(edge_key)

            d_from = get_dim_key(u_from)
            d_to = get_dim_key(u_to)

            # 2. Check intra-dimension conversion for dimensions with universal standards
            if d_from == d_to and isinstance(d_from, str):
                raise ValueError(
                    f"Redundant intra-dimension conversion between '{conv.from_unit}' and '{conv.to_unit}' "
                    f"for dimension '{d_from}' in ingredient '{self.id}'. "
                    f"Standard universal conversions already connect all units in this dimension."
                )

            # 3. Check double conversion across dimension pair (unordered, direction-invariant)
            dim_pair = frozenset([d_from, d_to])
            if dim_pair in seen_dim_pairs:
                d1_fmt, d2_fmt = sorted([format_dim(d_from), format_dim(d_to)])
                raise ValueError(
                    f"Double conversion across dimension pair '{d1_fmt}' <-> '{d2_fmt}' "
                    f"in ingredient '{self.id}' (attempted with '{conv.from_unit}' <-> '{conv.to_unit}'). "
                    f"Only a single conversion edge is permitted across any pair of dimensions."
                )
            seen_dim_pairs.add(dim_pair)

        return self

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

    def get_conversion_factor(self, from_unit: str, to_unit: str = "g") -> float | None:
        """Returns the conversion factor from from_unit to to_unit, or None."""
        u_from = from_unit.strip().lower()
        u_to = to_unit.strip().lower()
        for conv in self.conversions:
            c_from = conv.from_unit.strip().lower()
            c_to = conv.to_unit.strip().lower()
            if c_from == u_from and c_to == u_to:
                return conv.factor
            if c_to == u_from and c_from == u_to:
                return round(1.0 / conv.factor, 6)
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
