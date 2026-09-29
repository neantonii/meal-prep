"""Aisle taxonomy DTOs — deserialization and shape validation only.

Mirrors ``data/aisles.yaml``. No ordering or lookup helpers live here; those
concerns belong to a service built from these raw records.
"""

from pydantic import BaseModel, Field, field_validator

from meal_prep.dtos._normalize import normalize_slug


class Aisle(BaseModel):
    id: str = Field(..., description="Unique slug for the aisle, e.g. 'produce'")
    name: str = Field(..., description="Display name for the aisle, e.g. 'Produce'")
    order: int = Field(..., ge=1, description="Supermarket walking order (1-indexed)")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return normalize_slug(v, field="Aisle id")
