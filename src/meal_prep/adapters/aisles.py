"""YAML adapter for the aisle taxonomy (``data/aisles.yaml``)."""

from pathlib import Path

from meal_prep.adapters._yaml import read_yaml
from meal_prep.models.aisle import AislesConfig


def load_aisles(path: Path | str = Path("data/aisles.yaml")) -> AislesConfig:
    """Load and validate the aisles configuration from a YAML file."""
    file_path = Path(path)
    data = read_yaml(file_path, what="Aisles configuration")
    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML structure in {file_path}: expected dictionary root")
    return AislesConfig.model_validate(data)
