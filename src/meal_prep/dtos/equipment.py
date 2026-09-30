"""Equipment taxonomy DTOs — deserialization and shape validation only.

Mirrors ``data/equipment.yaml``. Cookware tokens in recipe bodies match ``id``
directly; there are no aliases.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from meal_prep.dtos._normalize import normalize_slug


class EquipmentItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        ..., description="Unique canonical equipment slug, e.g. 'air-fryer'"
    )
    name: str = Field(..., description="Display name, e.g. 'Air Fryer'")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return normalize_slug(v, field="Equipment id")
