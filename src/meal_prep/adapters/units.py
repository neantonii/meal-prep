"""YAML adapter for the units taxonomy (``data/units.yaml``)."""

from pathlib import Path

from meal_prep.adapters._yaml import read_yaml, require_root_key
from meal_prep.dtos.units import UnitsFileSchema


def load_units(path: Path | str = Path("data/units.yaml")) -> UnitsFileSchema:
    """Load and validate the units taxonomy from a YAML file."""
    file_path = Path(path)
    raw = read_yaml(file_path, what="Units configuration")
    return UnitsFileSchema.model_validate(require_root_key(raw, "units", file_path))
