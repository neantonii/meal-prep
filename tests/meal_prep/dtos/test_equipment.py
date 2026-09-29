"""Tests for the EquipmentItem DTO (``dtos/equipment.py``).

Happy paths plus our custom validation (``normalize_slug`` on the id) only.
Pydantic's implicit field constraints are not re-tested here.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from meal_prep.dtos.equipment import EquipmentItem


def test_equipment_valid():
    item = EquipmentItem.model_validate(
        {"id": "air-fryer", "name": "Air Fryer", "aliases": ["fryer"]}
    )
    assert item.id == "air-fryer"
    assert item.name == "Air Fryer"
    assert item.aliases == ["fryer"]


def test_equipment_id_is_normalized_to_slug():
    item = EquipmentItem.model_validate({"id": "  Air-Fryer  ", "name": "Air Fryer"})
    assert item.id == "air-fryer"


def test_equipment_aliases_default_to_empty_list():
    assert (
        EquipmentItem.model_validate({"id": "air-fryer", "name": "Air Fryer"}).aliases
        == []
    )


def test_equipment_id_invalid_slug_is_rejected():
    with pytest.raises(ValidationError, match="kebab-case slug"):
        EquipmentItem.model_validate({"id": "air_fryer", "name": "Air Fryer"})
