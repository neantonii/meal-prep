from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from meal_prep.models.enums import StorageType


class PackageInfo(BaseModel):
    container: str = Field(..., description="Container noun, e.g. pack, bag, carton, bottle, loaf")
    unit: str = Field(..., description="Unit noun of items in container, e.g. piece, slice, item, g, ml")
    amount: float = Field(..., gt=0, description="Amount of units in the container")

    @field_validator("container", "unit")
    @classmethod
    def clean_strings(cls, v: str) -> str:
        clean = v.strip().lower()
        if not clean:
            raise ValueError("Field cannot be empty")
        return clean


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
        clean = v.strip().lower()
        if not clean:
            raise ValueError("Unit cannot be empty")
        return clean

    @model_validator(mode="after")
    def validate_different_units(self) -> "UnitConversion":
        if self.from_unit == self.to_unit:
            raise ValueError(f"Conversion from unit '{self.from_unit}' to itself is redundant.")
        return self


class Ingredient(BaseModel):
    id: str = Field(..., description="Canonical unique slug, e.g. 'boneless-chicken-breast'")
    name: str = Field(..., description="Generic staple display name")
    aisle: str = Field(..., description="Supermarket aisle slug")
    storage: StorageType = Field(..., description="Storage temperature classification")
    shelf_life_days: int = Field(..., gt=0, description="Mandatory shelf life in days under this storage mode")

    package: PackageInfo
    reference: ReferenceInfo
    macros_per_100g: MacrosInfo
    conversions: list[UnitConversion] = Field(
        default_factory=list,
        description="Unit conversions bridging culinary units to grams. May be empty when the "
        "package unit is already a mass unit.",
    )

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        clean = v.strip().lower()
        if not clean:
            raise ValueError("Ingredient id cannot be empty")
        if not clean.replace("-", "").isalnum():
            raise ValueError(f"Ingredient id '{v}' must be alphanumeric with hyphens")
        return clean

