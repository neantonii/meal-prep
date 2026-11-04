"""Read and write ``<diary_dir>/staples.yaml`` (``meal_prep.dtos.staples``)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from meal_prep.adapters._yaml import read_yaml, write_yaml_atomic
from meal_prep.dtos.staples import StaplesDTO

STAPLES_FILE = "staples.yaml"


def load_staples(path: Path | str) -> StaplesDTO:
    """Load and validate the staples file; a missing file has no staples."""
    file_path = Path(path)
    if not file_path.exists():
        return StaplesDTO()
    data: Any = read_yaml(file_path, what="Staples")
    if data is None:
        return StaplesDTO()
    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML structure in {file_path}: expected a mapping")
    return StaplesDTO.model_validate(data)


def save_staples(path: Path | str, staples: StaplesDTO) -> Path:
    """Validate and atomically write the staples file."""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    return write_yaml_atomic(file_path, staples.model_dump(mode="json"))
