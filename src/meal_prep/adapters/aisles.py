"""YAML adapter for the aisle taxonomy (``data/aisles.yaml``)."""

from pathlib import Path

from meal_prep.adapters._yaml import read_yaml
from meal_prep.dtos.aisle import Aisle


def load_aisles(path: Path | str = Path("data/aisles.yaml")) -> list[Aisle]:
    """Load and validate the aisle taxonomy from a YAML file."""
    file_path = Path(path)
    data = read_yaml(file_path, what="Aisles configuration")
    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML structure in {file_path}: expected dictionary root")
    if not isinstance(data.get("aisles"), list):
        raise ValueError(f"Invalid YAML structure in {file_path}: expected 'aisles' list")
    return [Aisle.model_validate(item) for item in data["aisles"]]
