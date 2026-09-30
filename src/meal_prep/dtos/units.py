"""Units taxonomy DTOs — deserialization and shape validation only.

These models mirror ``data/units.yaml``. They carry raw authored values and
perform shape validation only; no normalization, lookup, or conversion logic
lives here. Registries (alias resolution, conversion) are built later by a
service from these raw records.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from meal_prep.dtos._normalize import clean_token


class ConversionStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: float = Field(..., gt=0)
    unit: str

    @field_validator("unit")
    @classmethod
    def clean_unit(cls, v: str) -> str:
        return clean_token(v, field="Conversion step unit")


class DimensionGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base: str
    allowed: dict[str, list[str]] = Field(default_factory=dict)
    conversions: dict[str, ConversionStep] = Field(default_factory=dict)

    @field_validator("base")
    @classmethod
    def clean_base(cls, v: str) -> str:
        return clean_token(v, field="Dimension base")

    @field_validator("allowed")
    @classmethod
    def clean_allowed(cls, v: dict[str, list[str]]) -> dict[str, list[str]]:
        cleaned: dict[str, list[str]] = {}
        for canonical, aliases in v.items():
            key = clean_token(canonical, field="Allowed unit")
            seen: set[str] = set()
            cleaned_aliases: list[str] = []
            for alias in aliases:
                a = clean_token(alias, field=f"Allowed unit '{canonical}' alias")
                if a in seen:
                    raise ValueError(
                        f"Duplicate alias '{alias}' for allowed unit '{canonical}'"
                    )
                seen.add(a)
                cleaned_aliases.append(a)
            cleaned[key] = cleaned_aliases
        return cleaned

    @field_validator("conversions")
    @classmethod
    def clean_conversion_keys(
        cls, v: dict[str, ConversionStep]
    ) -> dict[str, ConversionStep]:
        return {clean_token(k, field="Conversion key"): step for k, step in v.items()}


class UnitsFileSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mass: DimensionGroup
    volume: DimensionGroup
    package: DimensionGroup
    count: DimensionGroup = Field(default_factory=lambda: DimensionGroup(base="count"))
