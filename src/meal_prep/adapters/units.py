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
