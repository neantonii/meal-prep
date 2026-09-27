"""YAML adapter for the equipment taxonomy (``data/equipment.yaml``)."""

from pathlib import Path
import yaml

from meal_prep.models.equipment import EquipmentItem, EquipmentRegistry


def load_equipment(path: Path | str = Path("data/equipment.yaml")) -> EquipmentRegistry:
    """Load and validate equipment registry from a YAML file."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Equipment file not found at: {file_path}")

    with file_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict) or "equipment" not in data:
        raise ValueError(f"Invalid YAML structure in {file_path}: expected 'equipment' root key")

    items = [EquipmentItem.model_validate(item) for item in data["equipment"]]
    return EquipmentRegistry(items=items)
