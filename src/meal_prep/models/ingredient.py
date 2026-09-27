"""Enriched ingredient value — the frozen, fully-resolved form of an ingredient.

An ``Ingredient`` here is *not* the authored document (that is the DTO of the
same name in ``meal_prep.dtos.ingredient``); it is computed once by
``meal_prep.services.ingredients.prepare_ingredient`` and never constructed
from a file directly. It carries identity fields, the flattened reference
(brand/product/price), per-100g macros, and the ingredient's own frozen
conversion graph.

Both frozen dataclasses are value objects: no collaborators, no I/O, no
mutation. Methods are pure functions of the fields alone.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping

from meal_prep.engines.conversion_graph import ConversionGraph
from meal_prep.enums import StorageType


@dataclass(frozen=True, slots=True)
class MacrosInfo:
    """Nutritional values normalized to a per-100g basis.

    Every nutrient is a non-negative float; the optional nutrients from the
    authored DTO are coerced to ``0.0`` at enrichment, so consumers never have
    to handle ``None``.
    """

    calories_kcal: float
    protein_g: float
    fat_g: float
    carbs_g: float
    fiber_g: float
    saturated_fat_g: float
    sugars_g: float
    sodium_mg: float
    potassium_mg: float

    @classmethod
    def zero(cls) -> "MacrosInfo":
        """The additive identity — every nutrient at 0.0."""
        return cls(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    def scaled(self, factor: float) -> "MacrosInfo":
        """Multiply every nutrient by ``factor`` (raw, unrounded)."""
        return MacrosInfo(
            calories_kcal=self.calories_kcal * factor,
            protein_g=self.protein_g * factor,
            fat_g=self.fat_g * factor,
            carbs_g=self.carbs_g * factor,
            fiber_g=self.fiber_g * factor,
            saturated_fat_g=self.saturated_fat_g * factor,
            sugars_g=self.sugars_g * factor,
            sodium_mg=self.sodium_mg * factor,
            potassium_mg=self.potassium_mg * factor,
        )

    def added(self, other: "MacrosInfo") -> "MacrosInfo":
        """Element-wise sum with ``other`` (raw, unrounded)."""
        return MacrosInfo(
            calories_kcal=self.calories_kcal + other.calories_kcal,
            protein_g=self.protein_g + other.protein_g,
            fat_g=self.fat_g + other.fat_g,
            carbs_g=self.carbs_g + other.carbs_g,
            fiber_g=self.fiber_g + other.fiber_g,
            saturated_fat_g=self.saturated_fat_g + other.saturated_fat_g,
            sugars_g=self.sugars_g + other.sugars_g,
            sodium_mg=self.sodium_mg + other.sodium_mg,
            potassium_mg=self.potassium_mg + other.potassium_mg,
        )


@dataclass(frozen=True, slots=True)
class Ingredient:
    """An enriched, immutable ingredient ready for downstream computation."""

    id: str
    name: str
    aisle: str
    storage: StorageType
    shelf_life_days: int

    brand: str
    product: str
    price: float

    macros_per_100g: MacrosInfo
    custom_units: frozenset[str]
    synonyms: Mapping[str, str]
    conversion_graph: ConversionGraph

    package_weight_g: float
    price_per_100g: float

    def resolve(self, token: str) -> str:
        """Resolve a unit noun (e.g. a Cooklang token) to its canonical unit.

        Raises ``KeyError`` for an unregistered token; callers that need a
        friendly message check membership in ``synonyms`` first.
        """
        return self.synonyms[token]

    def factor(self, source: str, target: str) -> float | None:
        """Multiplication factor from ``source`` to ``target``, or ``None``."""
        return self.conversion_graph.factor(source, target)

    def can_convert(self, source: str, target: str) -> bool:
        """Whether a conversion path exists between ``source`` and ``target``."""
        return self.conversion_graph.can_convert(source, target)

    def convert(self, amount: float, source: str, target: str) -> float:
        """Convert ``amount`` from ``source`` to ``target`` (raw, unrounded)."""
        return self.conversion_graph.convert(amount, source, target)
