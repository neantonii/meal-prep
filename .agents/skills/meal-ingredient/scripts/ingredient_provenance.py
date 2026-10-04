"""Staged provenance for the ingredient review card.

The agent stages two files per review: a catalog entry in ``IngredientDTO``
shape (the exact mapping that graduates into ``data/ingredients/``) and a
provenance file validated here. The renderer cross-checks the two
(``check_against``), enriches via the real pipeline, and colors each value
white (``panel``) or yellow (``staged``).

Provenance has no defaults — every rendered value carries the agent's call.
It never enters the DTO or the catalog YAML.
"""

from __future__ import annotations

import sys
from enum import Enum
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / "src"))

from pydantic import BaseModel, ConfigDict, Field, field_validator  # noqa: E402

from meal_prep.dtos._normalize import clean_token, normalize_slug  # noqa: E402
from meal_prep.dtos.ingredient import IngredientDTO  # noqa: E402


class Provenance(str, Enum):
    """Where a staged value came from: label literal or agent judgment."""

    PANEL = "panel"
    STAGED = "staged"


def edge_key(from_unit: str, to_unit: str) -> str:
    """Canonical provenance key for a conversion edge."""
    return f"{from_unit}->{to_unit}"


def parse_edge_key(key: str) -> tuple[str, str]:
    """Split and clean a ``from->to`` provenance key."""
    parts = key.split("->")
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        raise ValueError(
            f"conversion provenance key '{key}' must look like 'package->g'"
        )
    return (
        clean_token(parts[0], field="Conversion provenance key"),
        clean_token(parts[1], field="Conversion provenance key"),
    )


_OPTIONAL_NUTRIENTS = ("saturated_fat_g", "sugars_g", "sodium_mg", "potassium_mg")


class IngredientProvenance(BaseModel):
    """Per-value provenance for one staged draft, nothing else.

    Scalar fields mirror the rendered DTO values; ``conversions`` holds one
    entry per DTO edge keyed ``from->to``. Null optional nutrients carry no
    marker — ``check_against`` enforces the presence match.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Draft slug; must match the DTO entry")
    id_provenance: Provenance
    name_provenance: Provenance
    step_name_provenance: Provenance
    aisle_provenance: Provenance
    storage_provenance: Provenance
    shelf_life_days_provenance: Provenance

    brand_provenance: Provenance
    product_provenance: Provenance
    price_provenance: Provenance

    calories_kcal_provenance: Provenance
    protein_g_provenance: Provenance
    fat_g_provenance: Provenance
    carbs_g_provenance: Provenance
    fiber_g_provenance: Provenance

    saturated_fat_g_provenance: Provenance | None = None
    sugars_g_provenance: Provenance | None = None
    sodium_mg_provenance: Provenance | None = None
    potassium_mg_provenance: Provenance | None = None

    basis_provenance: Provenance
    conversions: dict[str, Provenance] = Field(
        ..., description="Edge provenance keyed 'from->to', one per DTO edge"
    )

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return normalize_slug(v, field="Provenance id")

    @field_validator("conversions")
    @classmethod
    def normalize_edge_keys(cls, v: dict[str, Provenance]) -> dict[str, Provenance]:
        normalized: dict[str, Provenance] = {}
        for key, provenance in v.items():
            from_unit, to_unit = parse_edge_key(key)
            canonical = edge_key(from_unit, to_unit)
            if canonical in normalized:
                raise ValueError(f"duplicate conversion provenance for '{canonical}'")
            normalized[canonical] = provenance
        return normalized

    def check_against(self, dto: IngredientDTO) -> None:
        """Cross-check provenance against the staged DTO entry.

        Raises ``ValueError`` listing every mismatch: id, optional-nutrient
        presence, edge-set equality.
        """
        errors: list[str] = []
        if self.id != dto.id:
            errors.append(f"provenance id '{self.id}' != draft id '{dto.id}'")
        for field in _OPTIONAL_NUTRIENTS:
            has_value = getattr(dto.macros, field) is not None
            has_marker = getattr(self, f"{field}_provenance") is not None
            if has_value and not has_marker:
                errors.append(f"{field}_provenance is required when {field} is set")
            elif not has_value and has_marker:
                errors.append(
                    f"{field}_provenance must be omitted when {field} is null"
                )
        dto_edges = {edge_key(c.from_unit, c.to_unit) for c in dto.conversions}
        prov_edges = set(self.conversions)
        for missing in sorted(dto_edges - prov_edges):
            errors.append(f"conversion '{missing}' has no provenance entry")
        for extra in sorted(prov_edges - dto_edges):
            errors.append(f"provenance entry '{extra}' matches no draft conversion")
        if errors:
            raise ValueError("; ".join(errors))
