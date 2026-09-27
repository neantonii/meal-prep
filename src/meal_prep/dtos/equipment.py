"""Equipment taxonomy DTOs — deserialization and shape validation only.

Mirrors ``data/equipment.yaml``. No alias lookup or normalization lives here;
an equipment registry is built later by a service from these raw records.
"""

from pydantic import BaseModel, Field, field_validator

from meal_prep.dtos._normalize import normalize_slug


class EquipmentItem(BaseModel):
    id: str = Field(..., description="Unique canonical equipment slug, e.g. 'air-fryer'")
    name: str = Field(..., description="Display name, e.g. 'Air Fryer'")
    aliases: list[str] = Field(default_factory=list, description="Alternative names or spellings")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return normalize_slug(v, field="Equipment id")

