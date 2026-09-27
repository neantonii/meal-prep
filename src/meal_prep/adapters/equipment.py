"""YAML adapter for the equipment taxonomy (``data/equipment.yaml``)."""

from pathlib import Path

from meal_prep.adapters._yaml import read_yaml, require_root_key
from meal_prep.models.equipment import EquipmentItem, EquipmentRegistry


def load_equipment(path: Path | str = Path("data/equipment.yaml")) -> EquipmentRegistry:
    """Load and validate equipment registry from a YAML file."""
    file_path = Path(path)
    data = require_root_key(read_yaml(file_path, what="Equipment"), "equipment", file_path)
    items = [EquipmentItem.model_validate(item) for item in data]
    return EquipmentRegistry(items=items)
