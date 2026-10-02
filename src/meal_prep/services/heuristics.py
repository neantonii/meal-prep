"""Warn-only plausibility heuristics for enriched ingredients.

These checks are opinions about data quality, not validity: they never gate
enrichment and are never called by ``prepare_ingredient``. ``check_ingredient``
takes a prepared ``Ingredient`` and returns human-readable warning strings
(empty when nothing looks odd). Callers decide how to present them.
"""

from __future__ import annotations

from meal_prep.enums import StorageType
from meal_prep.models.ingredient import Ingredient

_ATWATER_TOLERANCE_KCAL = 25.0
_MACRO_SUM_LIMIT_G = 105.0

_SHELF_BANDS: dict[StorageType, tuple[int, int]] = {
    StorageType.AMBIENT: (7, 1095),
    StorageType.REFRIGERATED: (2, 90),
    StorageType.FROZEN: (180, 365),
}

# Keyed by lowercased aisle display name (matches the slug for current aisles).
# Aisles without a band (dairy, produce, bakery) are not price-checked.
_PRICE_BANDS: dict[str, tuple[float, float]] = {
    "meat": (2.00, 6.00),
    "seafood": (2.00, 6.00),
    "pantry": (0.20, 2.00),
    "spices": (2.00, 8.00),
}


def check_ingredient(ingredient: Ingredient) -> list[str]:
    """Return plausibility warnings for an enriched ingredient (possibly empty)."""
    warnings: list[str] = []
    macros = ingredient.macros_per_100g

    atwater = (
        4 * macros.protein_g + 4 * (macros.carbs_g - macros.fiber_g) + 9 * macros.fat_g
    )
    if abs(macros.calories_kcal - atwater) > _ATWATER_TOLERANCE_KCAL:
        warnings.append(
            f"atwater: label {macros.calories_kcal:.0f} kcal vs "
            f"macros-implied {atwater:.0f} kcal per 100g"
        )

    macro_sum = macros.protein_g + macros.fat_g + macros.carbs_g
    if macro_sum > _MACRO_SUM_LIMIT_G:
        warnings.append(
            f"macro-sum: protein+fat+carbs = {macro_sum:.1f}g "
            f"per 100g exceeds {_MACRO_SUM_LIMIT_G:.0f}g"
        )

    band = _PRICE_BANDS.get(ingredient.aisle_name.lower())
    if band is not None and not band[0] <= ingredient.price_per_100g <= band[1]:
        warnings.append(
            f"price: ${ingredient.price_per_100g:.2f}/100g outside "
            f"{ingredient.aisle_name} band ${band[0]:.2f}-${band[1]:.2f}"
        )

    shelf_lo, shelf_hi = _SHELF_BANDS[ingredient.storage]
    if not shelf_lo <= ingredient.shelf_life_days <= shelf_hi:
        warnings.append(
            f"shelf-life: {ingredient.shelf_life_days}d outside "
            f"{ingredient.storage.value} band {shelf_lo}-{shelf_hi}d"
        )

    return warnings
