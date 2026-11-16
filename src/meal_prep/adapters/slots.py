"""Read and write ``<diary_dir>/unassigned.yaml`` and ``<diary_dir>/bin.yaml``
(``meal_prep.dtos.slots``). A missing file is an empty slot."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel

from meal_prep.adapters._yaml import read_yaml, write_yaml_atomic
from meal_prep.dtos.slots import BinDTO, UnassignedDTO

UNASSIGNED_FILE = "unassigned.yaml"
BIN_FILE = "bin.yaml"


def _load[T: BaseModel](path: Path | str, model: type[T], what: str) -> T:
    file_path = Path(path)
    if not file_path.exists():
        return model()
    data: Any = read_yaml(file_path, what=what)
    if data is None:
        return model()
    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML structure in {file_path}: expected a mapping")
    return model.model_validate(data)


def _save(path: Path | str, dto: BaseModel) -> Path:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    return write_yaml_atomic(file_path, dto.model_dump(mode="json", exclude_none=True))


def load_unassigned(path: Path | str) -> UnassignedDTO:
    """Load and validate the unassigned slot; a missing file is empty."""
    return _load(path, UnassignedDTO, "Unassigned portions")


def save_unassigned(path: Path | str, slot: UnassignedDTO) -> Path:
    """Validate and atomically write the unassigned slot."""
    return _save(path, UnassignedDTO.model_validate(slot.model_dump()))


def load_bin(path: Path | str) -> BinDTO:
    """Load and validate the bin; a missing file is empty."""
    return _load(path, BinDTO, "Bin")


def save_bin(path: Path | str, slot: BinDTO) -> Path:
    """Validate and atomically write the bin."""
    return _save(path, BinDTO.model_validate(slot.model_dump()))
