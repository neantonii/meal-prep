"""Tests for the aisle YAML adapter (``adapters/aisles.py``).

Happy paths plus the adapter's own structure errors. The per-item shape
validation belongs to the ``Aisle`` DTO and is not re-tested here.
"""

from __future__ import annotations

import pytest

from meal_prep.adapters.aisles import load_aisles
from meal_prep.dtos.aisle import Aisle


def _write(tmp_path, text: str):
    path = tmp_path / "aisles.yaml"
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# happy paths
# ---------------------------------------------------------------------------


def test_load_aisles_valid(tmp_path):
    path = _write(
        tmp_path,
        "aisles:\n"
        "  - id: produce\n    name: Produce\n    order: 1\n"
        "  - id: bakery\n    name: Bakery\n    order: 2\n",
    )
    aisles = load_aisles(path)
    assert len(aisles) == 2
    assert isinstance(aisles[0], Aisle)
    assert aisles[0].id == "produce"
    assert aisles[1].id == "bakery"


def test_load_aisles_empty_list(tmp_path):
    aisles = load_aisles(_write(tmp_path, "aisles: []\n"))
    assert aisles == []


# ---------------------------------------------------------------------------
# structure errors
# ---------------------------------------------------------------------------


def test_load_aisles_rejects_list_root(tmp_path):
    with pytest.raises(ValueError, match="expected dictionary root"):
        load_aisles(_write(tmp_path, "- id: produce\n  name: Produce\n  order: 1\n"))


def test_load_aisles_rejects_missing_aisles_key(tmp_path):
    with pytest.raises(ValueError, match="expected 'aisles' list"):
        load_aisles(_write(tmp_path, "other: []\n"))


def test_load_aisles_rejects_non_list_aisles(tmp_path):
    with pytest.raises(ValueError, match="expected 'aisles' list"):
        load_aisles(_write(tmp_path, "aisles: {id: produce}\n"))


def test_load_aisles_missing_file():
    with pytest.raises(FileNotFoundError, match="Aisles configuration file not found"):
        load_aisles("/nonexistent/aisles.yaml")
