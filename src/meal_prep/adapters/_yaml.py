"""Shared YAML reading helpers for the taxonomy/catalog adapters."""

from pathlib import Path
from typing import Any

import yaml


def read_yaml(path: Path | str, *, what: str) -> Any:
    """Read a YAML file, raising a clear error if it is missing.

    Args:
        path: Path to the YAML file.
        what: Human-readable description used in the missing-file error.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"{what} file not found at: {file_path}")
    with file_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def require_root_key(data: Any, key: str, path: Path | str) -> Any:
    """Return ``data[key]``, requiring ``data`` to be a mapping containing ``key``."""
    if not isinstance(data, dict) or key not in data:
        raise ValueError(f"Invalid YAML structure in {path}: expected '{key}' root key")
    return data[key]


def write_yaml(path: Path | str, data: Any) -> Path:
    """Write ``data`` as YAML to ``path`` (overwriting), returning the path.

    The parent directory must already exist; creating directories is the
    caller's job.
    """
    file_path = Path(path)
    with file_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
    return file_path
