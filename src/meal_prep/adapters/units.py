"""YAML adapter for the units taxonomy (``data/units.yaml``)."""

from pathlib import Path

from meal_prep.adapters._yaml import read_yaml, require_root_key
from meal_prep.models.units import UnitsFileSchema, UnitsRegistry


def load_units(path: Path | str = Path("data/units.yaml")) -> UnitsRegistry:
    """Load and validate the units configuration from a YAML file."""
    file_path = Path(path)
    raw = read_yaml(file_path, what="Units configuration")
    schema = UnitsFileSchema.model_validate(require_root_key(raw, "units", file_path))
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
