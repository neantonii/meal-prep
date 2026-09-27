"""Tests for the units YAML adapter (``adapters/units.py``).

Happy paths plus the adapter's own structure error (via ``require_root_key``).
The shape of the ``units`` mapping belongs to ``UnitsFileSchema`` and is not
re-tested here.
"""

from __future__ import annotations

import pytest

from meal_prep.adapters.units import load_units
from meal_prep.dtos.units import UnitsFileSchema


def _write(tmp_path, text: str):
    path = tmp_path / "units.yaml"
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# happy paths
# ---------------------------------------------------------------------------


def test_load_units_valid(tmp_path):
    path = _write(
        tmp_path,
        "units:\n"
        "  mass:\n    base: g\n"
        "  volume:\n    base: ml\n"
        "  package:\n    base: package\n",
    )
    schema = load_units(path)
    assert isinstance(schema, UnitsFileSchema)
    assert schema.mass.base == "g"
    assert schema.volume.base == "ml"
    assert schema.package.base == "package"


# ---------------------------------------------------------------------------
# structure errors
# ---------------------------------------------------------------------------


def test_load_units_rejects_missing_root_key(tmp_path):
    with pytest.raises(ValueError, match="expected 'units' root key"):
        load_units(_write(tmp_path, "other: {}\n"))


def test_load_units_missing_file():
    with pytest.raises(FileNotFoundError, match="Units configuration file not found"):
        load_units("/nonexistent/units.yaml")
