"""YAML adapter for the aisle taxonomy (``data/aisles.yaml``)."""

from pathlib import Path
import yaml

from meal_prep.models.aisle import AislesConfig


def load_aisles(path: Path | str = Path("data/aisles.yaml")) -> AislesConfig:
    """Load and validate the aisles configuration from a YAML file."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Aisles configuration file not found at: {file_path}")

    with file_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML structure in {file_path}: expected dictionary root")

    return AislesConfig.model_validate(data)
