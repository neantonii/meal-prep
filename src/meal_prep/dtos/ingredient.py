from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from meal_prep.enums import StorageType
from meal_prep.dtos._normalize import clean_token, normalize_slug


class PackageInfo(BaseModel):
    container: str = Field(..., description="Container noun, e.g. pack, bag, carton, bottle, loaf")
    unit: str = Field(..., description="Unit noun of items in container, e.g. piece, slice, item, g, ml")
    amount: float = Field(..., gt=0, description="Amount of units in the container")

    @field_validator("container", "unit")
    @classmethod
    def clean_strings(cls, v: str) -> str:
        return clean_token(v, field="Package field")


class ReferenceInfo(BaseModel):
    brand: str = Field(..., description="Brand name, e.g. Compliments")
    product: str = Field(..., description="Full commercial product name")
    price: float = Field(..., gt=0, description="Retail purchase price in CAD")


class MacrosInfo(BaseModel):
    calories_kcal: float = Field(..., ge=0, description="Calories (kcal) per 100g")
    protein_g: float = Field(..., ge=0, description="Protein in grams per 100g")
    fat_g: float = Field(..., ge=0, description="Total fat in grams per 100g")
    carbs_g: float = Field(..., ge=0, description="Total carbohydrates in grams per 100g")
    fiber_g: float = Field(..., ge=0, description="Dietary fiber in grams per 100g")

    # Optional detailed nutrients
    saturated_fat_g: float | None = Field(None, ge=0, description="Saturated fat in grams per 100g")
    sugars_g: float | None = Field(None, ge=0, description="Total sugars in grams per 100g")
    sodium_mg: float | None = Field(None, ge=0, description="Sodium in milligrams per 100g")
    potassium_mg: float | None = Field(None, ge=0, description="Potassium in milligrams per 100g")


class UnitConversion(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_unit: str = Field(..., alias="from", description="Source measurement unit")
    to_unit: str = Field(..., alias="to", description="Target measurement unit")
    factor: float = Field(..., gt=0, description="Multiplier such that 1 from_unit = factor * to_unit")

    @field_validator("from_unit", "to_unit")
    @classmethod
    def clean_units(cls, v: str) -> str:
        return clean_token(v, field="Unit")

    @model_validator(mode="after")
    def validate_different_units(self) -> "UnitConversion":
        if self.from_unit == self.to_unit:
            raise ValueError(f"Conversion from unit '{self.from_unit}' to itself is redundant.")
        return self


class Ingredient(BaseModel):
    """Ingredient DTO — the authored, validated ingredient document.

    Decodes ``data/ingredients/<aisle>.yaml`` and carries raw authored values.
    The enriched ``Ingredient`` (in ``meal_prep.models``) is computed later by a
    service (``prepare_ingredient``). The two share a name and are distinguished
    by import path, not by suffix or underscore.
    """
    id: str = Field(..., description="Canonical unique slug, e.g. 'boneless-chicken-breast'")
    name: str = Field(..., description="Generic staple display name")
    aisle: str = Field(..., description="Supermarket aisle slug")
    storage: StorageType = Field(..., description="Storage temperature classification")
    shelf_life_days: int = Field(..., gt=0, description="Mandatory shelf life in days under this storage mode")

    package: PackageInfo
    reference: ReferenceInfo
    macros_per_100g: MacrosInfo
    custom_units: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Explicitly registered non-standard units (canonical -> aliases), in the "
        "same shape as the standard `allowed` map in units.yaml.",
    )
    conversions: list[UnitConversion] = Field(
        default_factory=list,
        description="Unit conversions bridging culinary units to grams. May be empty when the "
        "package unit is already a mass unit.",
    )

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return normalize_slug(v, field="Ingredient id")

    @field_validator("custom_units")
    @classmethod
    def validate_custom_units(cls, v: dict[str, list[str]]) -> dict[str, list[str]]:
        """Normalize custom-unit tokens: canonical keys and aliases.

        Custom units follow the same identifier convention as ids (kebab-case)
        and the same alias cleanup as standard units (case-fold + trim only).
        No inference, no plural stripping, no magic.
        """
        cleaned: dict[str, list[str]] = {}
        for canonical, aliases in v.items():
            key = normalize_slug(canonical, field="Custom unit")
            seen: set[str] = set()
            cleaned_aliases: list[str] = []
            for alias in aliases:
                a = clean_token(alias, field=f"Custom unit '{canonical}' alias")
                if a in seen:
                    raise ValueError(f"Duplicate alias '{alias}' for custom unit '{canonical}'")
                seen.add(a)
                cleaned_aliases.append(a)
            if key not in seen:
                cleaned_aliases.insert(0, key)
            cleaned[key] = cleaned_aliases
        return cleaned

