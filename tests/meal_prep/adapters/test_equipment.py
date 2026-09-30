"""Tests for the equipment YAML adapter (``adapters/equipment.py``).

Happy paths plus the adapter's own structure error (via ``require_root_key``).
Per-item shape validation belongs to ``EquipmentItem`` and is not re-tested.
"""

from __future__ import annotations

import pytest

from meal_prep.adapters.equipment import load_equipment
from meal_prep.dtos.equipment import EquipmentItem


def _write(tmp_path, text: str):
    path = tmp_path / "equipment.yaml"
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# happy paths
# ---------------------------------------------------------------------------


def test_load_equipment_valid(tmp_path):
    path = _write(
        tmp_path,
        "equipment:\n"
        "  - id: air-fryer\n    name: Air Fryer\n    aliases: [air-fryer, airfryer]\n"
        "  - id: skillet\n    name: Skillet\n",
    )
    items = load_equipment(path)
    assert len(items) == 2
    assert isinstance(items[0], EquipmentItem)
    assert items[0].id == "air-fryer"
    assert items[0].aliases == ["air-fryer", "airfryer"]
    assert items[1].aliases == []


# ---------------------------------------------------------------------------
# structure errors
# ---------------------------------------------------------------------------


def test_load_equipment_rejects_missing_root_key(tmp_path):
    with pytest.raises(ValueError, match="expected 'equipment' root key"):
        load_equipment(_write(tmp_path, "other: []\n"))


def test_load_equipment_rejects_non_mapping_root(tmp_path):
    with pytest.raises(ValueError, match="expected 'equipment' root key"):
        load_equipment(_write(tmp_path, "- id: air-fryer\n  name: Air Fryer\n"))


def test_load_equipment_missing_file():
    with pytest.raises(FileNotFoundError, match="Equipment file not found"):
        load_equipment("/nonexistent/equipment.yaml")
