"""Tests for the shared YAML reading helpers (``adapters/_yaml.py``).

These are the lowest-level I/O helpers every adapter builds on, so the tests
pin down the error contract precisely: missing files raise ``FileNotFoundError``
with the human-readable ``what`` description, and ``require_root_key`` fails on
a non-mapping or absent key.
"""

from __future__ import annotations

import pytest
import yaml

from meal_prep.adapters._yaml import read_yaml, require_root_key

# ---------------------------------------------------------------------------
# read_yaml
# ---------------------------------------------------------------------------


def test_read_yaml_missing_file_raises_with_what(tmp_path):
    missing = tmp_path / "nope.yaml"
    with pytest.raises(FileNotFoundError, match="Units configuration file not found"):
        read_yaml(missing, what="Units configuration")


def test_read_yaml_loads_mapping(tmp_path):
    path = tmp_path / "units.yaml"
    path.write_text("mass:\n  base: g\n", encoding="utf-8")
    assert read_yaml(path, what="Units") == {"mass": {"base": "g"}}


def test_read_yaml_loads_list(tmp_path):
    path = tmp_path / "items.yaml"
    path.write_text("- a\n- b\n", encoding="utf-8")
    assert read_yaml(path, what="Items") == ["a", "b"]


def test_read_yaml_empty_file_returns_none(tmp_path):
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")
    assert read_yaml(path, what="Empty") is None


def test_read_yaml_accepts_str_or_path(tmp_path):
    path = tmp_path / "x.yaml"
    path.write_text("key: value\n", encoding="utf-8")
    assert read_yaml(str(path), what="X") == {"key": "value"}
    assert read_yaml(path, what="X") == {"key": "value"}


def test_read_yaml_invalid_syntax_raises_yaml_error(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("a: [unclosed\n", encoding="utf-8")
    with pytest.raises(yaml.YAMLError):
        read_yaml(path, what="Bad")


# ---------------------------------------------------------------------------
# require_root_key
# ---------------------------------------------------------------------------


def test_require_root_key_returns_value(tmp_path):
    assert require_root_key({"units": {"mass": {}}}, "units", tmp_path / "u.yaml") == {
        "mass": {}
    }


def test_require_root_key_missing_key_raises(tmp_path):
    with pytest.raises(ValueError, match="expected 'units' root key"):
        require_root_key({"other": 1}, "units", tmp_path / "u.yaml")


def test_require_root_key_non_mapping_raises(tmp_path):
    with pytest.raises(ValueError, match="expected 'units' root key"):
        require_root_key(["not", "a", "mapping"], "units", tmp_path / "u.yaml")


def test_require_root_key_none_raises(tmp_path):
    with pytest.raises(ValueError, match="expected 'units' root key"):
        require_root_key(None, "units", tmp_path / "u.yaml")
