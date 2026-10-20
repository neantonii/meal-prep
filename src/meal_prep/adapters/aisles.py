"""YAML adapter for the aisle taxonomy (``data/aisles.yaml``)."""

from pathlib import Path

from meal_prep.adapters._yaml import read_yaml
from meal_prep.dtos.aisle import Aisle


def load_aisles(path: Path | str = Path("data/aisles.yaml")) -> list[Aisle]:
    """Load and validate the aisle taxonomy from a YAML file.

    Aisle ``order`` values must be unique: two aisles sharing an order would
    render in arbitrary relative order.
    """
    file_path = Path(path)
    data = read_yaml(file_path, what="Aisles configuration")
    if not isinstance(data, dict):
        raise ValueError(
            f"Invalid YAML structure in {file_path}: expected dictionary root"
        )
    if not isinstance(data.get("aisles"), list):
        raise ValueError(
            f"Invalid YAML structure in {file_path}: expected 'aisles' list"
        )
    aisles = [Aisle.model_validate(item) for item in data["aisles"]]
    seen: dict[int, str] = {}
    for aisle in aisles:
        if aisle.order in seen:
            raise ValueError(
                f"Duplicate aisle order {aisle.order} in {file_path}: "
                f"'{seen[aisle.order]}' and '{aisle.id}' share it."
            )
        seen[aisle.order] = aisle.id
    return aisles
