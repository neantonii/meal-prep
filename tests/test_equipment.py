from pathlib import Path
import pytest
from pydantic import ValidationError
from meal_prep.models.equipment import EquipmentItem, EquipmentRegistry, load_equipment


@pytest.fixture
def registry():
    return load_equipment(Path("data/equipment.yaml"))


def test_load_real_equipment_yaml(registry):
    assert len(registry.items) == 10
    assert "air_fryer" in registry.canonical_ids
    assert "rice_cooker" in registry.canonical_ids
    assert "skillet" in registry.canonical_ids
    assert "sheet_pan" in registry.canonical_ids
    assert "meat_thermometer" in registry.canonical_ids


def test_normalize_aliases(registry):
    # Air fryer aliases
    assert registry.normalize("air fryer") == "air_fryer"
    assert registry.normalize("air-fryer") == "air_fryer"
    assert registry.normalize("airfryer") == "air_fryer"

    # Skillet aliases
    assert registry.normalize("frying pan") == "skillet"
    assert registry.normalize("pan") == "skillet"
    assert registry.normalize("large non-stick skillet") == "skillet"

    # Sheet pan aliases
    assert registry.normalize("baking sheet") == "sheet_pan"
    assert registry.normalize("baking tray") == "sheet_pan"

    # Blender aliases
    assert registry.normalize("food processor") == "blender"
    assert registry.normalize("immersion blender") == "blender"


def test_get_equipment_item(registry):
    item = registry.get("frying pan")
    assert item is not None
    assert item.id == "skillet"
    assert item.name == "Large Non-Stick Skillet"

    assert registry.get("nonexistent_device") is None


def test_unknown_equipment_raises_error(registry):
    with pytest.raises(ValueError, match="Unknown equipment: 'laser_gun'"):
        registry.normalize("laser_gun")


def test_duplicate_id_raises_error():
    data = {
        "items": [
            EquipmentItem(id="air_fryer", name="Air Fryer"),
            EquipmentItem(id="air_fryer", name="Duplicate Air Fryer"),
        ]
    }
    with pytest.raises(ValidationError, match="Duplicate equipment id"):
        EquipmentRegistry.model_validate(data)
