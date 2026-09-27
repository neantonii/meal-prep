from pydantic import BaseModel, Field, field_validator, model_validator


class Aisle(BaseModel):
    id: str = Field(..., description="Unique slug for the aisle, e.g. 'produce'")
    name: str = Field(..., description="Display name for the aisle, e.g. 'Produce'")
    order: int = Field(..., ge=1, description="Supermarket walking order (1-indexed)")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if not cleaned:
            raise ValueError("Aisle id cannot be empty")
        if not cleaned.replace("_", "").replace("-", "").isalnum():
            raise ValueError(f"Aisle id '{v}' must be alphanumeric with underscores or dashes")
        return cleaned


class AislesConfig(BaseModel):
    aisles: list[Aisle]

    @model_validator(mode="after")
    def validate_unique_ids_and_orders(self) -> "AislesConfig":
        ids = set()
        orders = set()
        for aisle in self.aisles:
            if aisle.id in ids:
                raise ValueError(f"Duplicate aisle id found: '{aisle.id}'")
            ids.add(aisle.id)

            if aisle.order in orders:
                raise ValueError(f"Duplicate aisle order found: {aisle.order} for aisle '{aisle.id}'")
            orders.add(aisle.order)
        return self

    @property
    def ordered_aisles(self) -> list[Aisle]:
        return sorted(self.aisles, key=lambda a: a.order)

    @property
    def valid_ids(self) -> set[str]:
        return {a.id for a in self.aisles}

    def get(self, aisle_id: str) -> Aisle | None:
        target = aisle_id.strip().lower()
        for a in self.aisles:
            if a.id == target:
                return a
        return None

    def to_cooklang_headers(self) -> list[str]:
        """Returns ordered section headers for Cooklang aisle.conf."""
        return [f"[{a.id}]" for a in self.ordered_aisles]

