from pathlib import Path
from typing import Any
import yaml
from pydantic import BaseModel, Field, model_validator


class ConversionStep(BaseModel):
    amount: float
    unit: str


class DimensionGroup(BaseModel):
    base: str
    allowed: dict[str, list[str]] = Field(default_factory=dict)
    conversions: dict[str, ConversionStep] = Field(default_factory=dict)

    @property
    def canonical_units(self) -> set[str]:
        return set(self.allowed.keys())


class UnitsFileSchema(BaseModel):
    mass: DimensionGroup
    volume: DimensionGroup
    count: DimensionGroup
    time: DimensionGroup
    packaging_containers: list[str]


class UnitsRegistry(BaseModel):
    schema_data: UnitsFileSchema

    def __init__(self, **data: Any):
        super().__init__(**data)
        # Build lookup table: alias -> (canonical_name, dimension)
        self._alias_map: dict[str, tuple[str, str]] = {}
        for dim_name in ("mass", "volume", "count", "time"):
            group: DimensionGroup = getattr(self.schema_data, dim_name)
            for canonical, aliases in group.allowed.items():
                self._alias_map[canonical.lower()] = (canonical, dim_name)
                for alias in aliases:
                    self._alias_map[alias.lower()] = (canonical, dim_name)

    def normalize(self, unit_name: str) -> str:
        """Returns the canonical unit name for any recognized alias."""
        clean = unit_name.strip().lower()
        if clean in self._alias_map:
            return self._alias_map[clean][0]
        raise ValueError(f"Unknown unit: '{unit_name}'. Not found in allowed units registry.")

    def dimension_of(self, unit_name: str) -> str:
        """Returns the dimension ('mass', 'volume', 'count') of a unit."""
        clean = unit_name.strip().lower()
        if clean in self._alias_map:
            return self._alias_map[clean][1]
        raise ValueError(f"Unknown unit: '{unit_name}'. Cannot determine dimension.")

    def is_valid_unit(self, unit_name: str) -> bool:
        return unit_name.strip().lower() in self._alias_map

    def is_valid_container(self, container_name: str) -> bool:
        clean = container_name.strip().lower()
        return clean in [c.lower() for c in self.schema_data.packaging_containers]

    def is_valid_time_unit(self, unit_name: str) -> bool:
        """Check if unit is a registered time duration unit (s, min, hr, etc.)."""
        clean = unit_name.strip().lower()
        return clean in self._alias_map and self._alias_map[clean][1] == "time"

    def to_base(self, amount: float, unit_name: str) -> tuple[float, str]:
        """Converts an amount to its dimension's base unit (g, ml, or item)."""
        canonical = self.normalize(unit_name)
        dim = self.dimension_of(canonical)
        group: DimensionGroup = getattr(self.schema_data, dim)

        if canonical == group.base:
            return amount, group.base

        if canonical in group.conversions:
            conv = group.conversions[canonical]
            # If target of conversion is the base unit:
            if conv.unit == group.base:
                return amount * conv.amount, group.base
            # If multi-step within universal conversions:
            sub_amount, sub_unit = self.to_base(conv.amount, conv.unit)
            return amount * sub_amount, sub_unit

        # If it's a count unit (like slice, clove) without a global mass conversion:
        if dim == "count":
            return amount, canonical

        raise ValueError(f"No universal conversion defined from '{canonical}' to base '{group.base}'")

    def convert(self, amount: float, from_unit: str, to_unit: str) -> float:
        """Converts between two compatible units of the same physical dimension."""
        from_canonical = self.normalize(from_unit)
        to_canonical = self.normalize(to_unit)

        from_dim = self.dimension_of(from_canonical)
        to_dim = self.dimension_of(to_canonical)

        if from_dim != to_dim:
            raise ValueError(
                f"Cannot convert between different dimensions: '{from_unit}' ({from_dim}) and '{to_unit}' ({to_dim}). "
                "Ingredient-specific density conversion is required."
            )

        # Convert from_unit to base, then base to to_unit
        base_amount, _ = self.to_base(amount, from_canonical)
        to_base_factor, _ = self.to_base(1.0, to_canonical)

        return base_amount / to_base_factor


def load_units(path: Path | str = Path("data/units.yaml")) -> UnitsRegistry:
    """Load and validate the units configuration from a YAML file."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Units configuration file not found at: {file_path}")

    with file_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict) or "units" not in raw:
        raise ValueError(f"Invalid YAML structure in {file_path}: expected 'units' root key")

    schema = UnitsFileSchema.model_validate(raw["units"])
    return UnitsRegistry(schema_data=schema)


_DEFAULT_UNITS_REGISTRY: UnitsRegistry | None = None


def get_default_units(units_path: Path | str | None = None) -> UnitsRegistry:
    """Get or load singleton default UnitsRegistry."""
    global _DEFAULT_UNITS_REGISTRY
    if units_path is not None:
        return load_units(units_path)
    if _DEFAULT_UNITS_REGISTRY is None:
        default_file = Path("data/units.yaml")
        if not default_file.exists():
            default_file = Path(__file__).resolve().parent.parent.parent.parent / "data" / "units.yaml"
        _DEFAULT_UNITS_REGISTRY = load_units(default_file)
    return _DEFAULT_UNITS_REGISTRY

