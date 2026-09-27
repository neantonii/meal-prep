"""Units taxonomy DTOs — deserialization and shape validation only.

These models mirror ``data/units.yaml``. They carry raw authored values and
perform shape validation only; no normalization, lookup, or conversion logic
lives here. Registries (alias resolution, conversion) are built later by a
service from these raw records.
"""

from pydantic import BaseModel, Field


class ConversionStep(BaseModel):
    amount: float
    unit: str


class DimensionGroup(BaseModel):
    base: str
    allowed: dict[str, list[str]] = Field(default_factory=dict)
    conversions: dict[str, ConversionStep] = Field(default_factory=dict)


class UnitsFileSchema(BaseModel):
    mass: DimensionGroup
    volume: DimensionGroup
