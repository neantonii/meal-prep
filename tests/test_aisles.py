from pathlib import Path
import pytest
from pydantic import ValidationError
from meal_prep.models.aisle import Aisle, AislesConfig, load_aisles


def test_load_real_aisles_yaml():
    config = load_aisles(Path("data/aisles.yaml"))
    assert len(config.aisles) == 7

    ordered = [a.id for a in config.ordered_aisles]
    assert ordered == ["produce", "bakery", "meat", "seafood", "dairy", "pantry", "spices"]

    assert config.get("meat") is not None
    assert config.get("meat").name == "Meat"
    assert config.get("meat").order == 3
    assert config.get("nonexistent") is None


def test_to_cooklang_headers():
    config = load_aisles(Path("data/aisles.yaml"))
    headers = config.to_cooklang_headers()
    assert headers == [
        "[produce]",
        "[bakery]",
        "[meat]",
        "[seafood]",
        "[dairy]",
        "[pantry]",
        "[spices]",
    ]


def test_duplicate_id_raises_error():
    data = {
        "aisles": [
            {"id": "produce", "name": "Produce", "order": 1},
            {"id": "produce", "name": "Produce Duplicate", "order": 2},
        ]
    }
    with pytest.raises(ValidationError, match="Duplicate aisle id"):
        AislesConfig.model_validate(data)


def test_duplicate_order_raises_error():
    data = {
        "aisles": [
            {"id": "produce", "name": "Produce", "order": 1},
            {"id": "meat", "name": "Meat", "order": 1},
        ]
    }
    with pytest.raises(ValidationError, match="Duplicate aisle order"):
        AislesConfig.model_validate(data)


def test_invalid_order_negative():
    data = {
        "aisles": [
            {"id": "produce", "name": "Produce", "order": 0},
        ]
    }
    with pytest.raises(ValidationError):
        AislesConfig.model_validate(data)
