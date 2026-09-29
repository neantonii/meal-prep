from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from meal_prep.enums import StorageType
from meal_prep.dtos._normalize import clean_token, normalize_slug


class ReferenceInfo(BaseModel):
    brand: str = Field(..., description="Brand name, e.g. Compliments")
    product: str = Field(..., description="Full commercial product name")
    price: float = Field(..., gt=0, description="Retail purchase price in CAD")


class MacrosInfo(BaseModel):
    """Authored nutrition values, expressed *per* a serving basis.

    The nutrients are not necessarily per 100g: Canadian labels usually print
    "per <amount> <unit>" (e.g. "per 55 g", "per 1/3 cup"). The ``unit`` and
    ``amount`` fields record that basis; enrichment scales the values to a
    per-100g standard using the conversion graph.
    """
    unit: str = Field(..., min_length=1, description="Serving basis unit, e.g. 'g' or 'cup'")
    amount: float = Field(..., gt=0, description="Serving basis quantity, e.g. 100 or 0.333")

    calories_kcal: float = Field(..., ge=0, description="Calories (kcal) per the basis amount")
    protein_g: float = Field(..., ge=0, description="Protein in grams per the basis amount")
    fat_g: float = Field(..., ge=0, description="Total fat in grams per the basis amount")
    carbs_g: float = Field(..., ge=0, description="Total carbohydrates in grams per the basis amount")
    fiber_g: float = Field(..., ge=0, description="Dietary fiber in grams per the basis amount")

    # Optional detailed nutrients
    saturated_fat_g: float | None = Field(None, ge=0, description="Saturated fat in grams per the basis amount")
    sugars_g: float | None = Field(None, ge=0, description="Total sugars in grams per the basis amount")
    sodium_mg: float | None = Field(None, ge=0, description="Sodium in milligrams per the basis amount")
    potassium_mg: float | None = Field(None, ge=0, description="Potassium in milligrams per the basis amount")

    @field_validator("unit")
    @classmethod
    def clean_unit(cls, v: str) -> str:
        return clean_token(v, field="Macros basis unit")


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
    step_name: str | None = Field(
        None,
        description="Optional prose-friendly noun for instruction text (e.g. 'chicken "
        "breasts'). Falls back to `name` when absent.",
    )
    aisle: str = Field(..., description="Supermarket aisle slug")
    storage: StorageType = Field(..., description="Storage temperature classification")
    shelf_life_days: int = Field(..., gt=0, description="Mandatory shelf life in days under this storage mode")

    reference: ReferenceInfo
    macros: MacrosInfo
    custom_units: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Explicitly registered non-standard units (canonical -> aliases), in the "
        "same shape as the standard `allowed` map in units.yaml.",
    )
    conversions: list[UnitConversion] = Field(
        default_factory=list,
        description="Unit conversions. The reserved `package` node's retail edge is authored "
        "here as `{from: package, to: <unit>, factor: <amount>}`.",
    )

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return normalize_slug(v, field="Ingredient id")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        # First character must be a capital letter.
        if not (v and v[0].isalpha() and v[0].isupper()):
            raise ValueError(f"Ingredient name must start with a capital letter, got '{v}'.")
        return v

    @field_validator("step_name")
    @classmethod
    def validate_step_name(cls, v: str | None) -> str | None:
        # Optional; when present, first character must be a lowercase letter.
        if v is not None and not (v and v[0].isalpha() and v[0].islower()):
            raise ValueError(f"Ingredient step_name must start with a lowercase letter, got '{v}'.")
        return v

    @field_validator("custom_units")
    @classmethod
    def validate_custom_units(cls, v: dict[str, list[str]]) -> dict[str, list[str]]:
        """Normalize custom-unit tokens: canonical keys and aliases.

        Custom units follow the same identifier convention as ids (kebab-case)
        and the same alias cleanup as standard units (case-fold + trim only).
        Aliases are stored exactly as authored — the canonical key is *not*
        auto-inserted, mirroring the standard `allowed` map, which also requires
        the canonical to be listed explicitly. No inference, no plural
        stripping, no magic.
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
            cleaned[key] = cleaned_aliases
        return cleaned

