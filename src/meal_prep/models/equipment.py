from typing import Any
from pydantic import BaseModel, Field, field_validator, model_validator


class EquipmentItem(BaseModel):
    id: str = Field(..., description="Unique canonical equipment slug, e.g. 'air_fryer'")
    name: str = Field(..., description="Display name, e.g. 'Air Fryer'")
    aliases: list[str] = Field(default_factory=list, description="Alternative names or spellings")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if not cleaned:
            raise ValueError("Equipment id cannot be empty")
        if not cleaned.replace("_", "").replace("-", "").isalnum():
            raise ValueError(f"Equipment id '{v}' must be alphanumeric with underscores or dashes")
        return cleaned


class EquipmentRegistry(BaseModel):
    items: list[EquipmentItem]

    def __init__(self, **data: Any):
        super().__init__(**data)
        self._lookup: dict[str, EquipmentItem] = {}
        for item in self.items:
            # Map canonical id and hyphen/underscore variants
            self._lookup[item.id.lower()] = item
            self._lookup[item.id.lower().replace("_", "-")] = item
            # Map display name
            self._lookup[item.name.lower()] = item
            # Map all aliases and their hyphen/underscore variants
            for alias in item.aliases:
                clean_alias = alias.strip().lower()
                self._lookup[clean_alias] = item
                self._lookup[clean_alias.replace("_", "-")] = item
                self._lookup[clean_alias.replace(" ", "-")] = item

    @model_validator(mode="after")
    def validate_unique_ids(self) -> "EquipmentRegistry":
        ids = set()
        for item in self.items:
            if item.id in ids:
                raise ValueError(f"Duplicate equipment id found: '{item.id}'")
            ids.add(item.id)
        return self

    @property
    def canonical_ids(self) -> set[str]:
        return {item.id for item in self.items}

    def normalize(self, name_or_alias: str) -> str:
        """Returns the canonical id for any recognized equipment alias."""
        clean = name_or_alias.strip().lower()
        if clean in self._lookup:
            return self._lookup[clean].id
        raise ValueError(f"Unknown equipment: '{name_or_alias}'. Not found in equipment registry.")

    def get(self, name_or_alias: str) -> EquipmentItem | None:
        """Returns the EquipmentItem for any recognized alias or id, or None."""
        clean = name_or_alias.strip().lower()
        return self._lookup.get(clean)

    def is_valid(self, name_or_alias: str) -> bool:
        return name_or_alias.strip().lower() in self._lookup

