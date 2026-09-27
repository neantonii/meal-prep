"""YAML adapter for the units taxonomy (``data/units.yaml``)."""

from pathlib import Path
import yaml

from meal_prep.models.units import UnitsFileSchema, UnitsRegistry


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
