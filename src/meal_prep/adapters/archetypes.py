"""YAML adapter for the meal archetypes (``data/archetypes.yaml``)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from meal_prep.adapters._yaml import read_yaml
from meal_prep.dtos.archetypes import ArchetypesDTO


def load_archetypes(path: Path | str) -> ArchetypesDTO:
    """Load and validate the archetypes file (shape only)."""
    file_path = Path(path)
    data: Any = read_yaml(file_path, what="Archetypes")
    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML structure in {file_path}: expected a mapping")
    return ArchetypesDTO.model_validate(data)
