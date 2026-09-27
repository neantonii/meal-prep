"""Ingredient pricing/conversion helpers.

Temporary service functions for the derived ingredient values that need the
conversion graph (and therefore the units registry) but currently live on the
``Ingredient`` model. Callers pass the ingredient and registry explicitly; the
per-ingredient conversion graph is cached on the ingredient via its private
attr so it is only built once.

TODO(services): settle the real service shape (an ``IngredientService`` or
similar) rather than these module-level functions.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from meal_prep.models.ingredient import Ingredient
    from meal_prep.models.units import UnitsRegistry


def container_weight_g(ingredient: "Ingredient", units: "UnitsRegistry") -> float:
    """Container net weight in grams, derived from the conversion graph.

    Returns 0.0 when the container cannot reach grams; post-load validation
    reports that as an error.
    """
    graph = ingredient.get_conversion_graph(units)
    factor = graph.factor(ingredient.package.container, "g")
    return factor if factor is not None else 0.0


def price_per_100g(ingredient: "Ingredient", units: "UnitsRegistry") -> float:
    """Calculated retail unit price per 100g in CAD."""
    return round((ingredient.reference.price / container_weight_g(ingredient, units)) * 100, 2)


def price_per_kg(ingredient: "Ingredient", units: "UnitsRegistry") -> float:
    """Calculated retail unit price per kg in CAD."""
    return round(price_per_100g(ingredient, units) * 10, 2)


def price_per_unit(ingredient: "Ingredient") -> float:
    """Calculated price per individual package unit (e.g. per piece, slice, egg, ml, or g)."""
    return round(ingredient.reference.price / ingredient.package.amount, 4)
