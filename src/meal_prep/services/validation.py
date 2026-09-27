"""Collaborative ingredient validation.

Temporary service functions for the conversion cross-checks that need the
units registry (and therefore cannot live on the pure ``Ingredient`` model).
Called from the ingredients adapter at load time, once the registry is in
scope.

TODO(services): settle the real service shape later.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from meal_prep.models.ingredient import Ingredient
    from meal_prep.models.units import UnitsRegistry


def validate_conversions(ingredient: "Ingredient", units: "UnitsRegistry") -> None:
    """Reject redundant/conflicting authored conversions (dimension cross-check).

    Rules:
    1. No duplicate edges (e.g. defining A -> B twice, or both A -> B and B -> A).
    2. No intra-dimension conversions for dimensions that already have universal
       conversions (e.g. tbsp -> tsp, or kg -> g).
    3. No double conversion across the same pair of dimensions (e.g. both
       tbsp -> g and tsp -> g).
    """
    def get_dim_key(unit_name: str) -> str | tuple[str, str]:
        clean = unit_name.strip().lower()
        if units.is_valid_unit(clean):
            canonical = units.normalize(clean)
            dim = units.dimension_of(canonical)
            group = getattr(units.schema_data, dim, None)
            if group and group.conversions:
                return dim
            return (dim, canonical)
        return ("discrete", clean)

    def format_dim(dim_key: str | tuple[str, str]) -> str:
        if isinstance(dim_key, tuple):
            return f"{dim_key[0]}:{dim_key[1]}"
        return dim_key

    seen_edges: set[frozenset[str]] = set()
    seen_dim_pairs: set[frozenset[str | tuple[str, str]]] = set()

    for conv in ingredient.conversions:
        u_from = conv.from_unit.strip().lower()
        if units.is_valid_unit(u_from):
            u_from = units.normalize(u_from)

        u_to = conv.to_unit.strip().lower()
        if units.is_valid_unit(u_to):
            u_to = units.normalize(u_to)

        edge_key = frozenset([u_from, u_to])
        if edge_key in seen_edges:
            raise ValueError(
                f"Duplicate conversion between '{conv.from_unit}' and '{conv.to_unit}' "
                f"defined in ingredient '{ingredient.id}'."
            )
        seen_edges.add(edge_key)

        d_from = get_dim_key(u_from)
        d_to = get_dim_key(u_to)

        if d_from == d_to and isinstance(d_from, str):
            raise ValueError(
                f"Redundant intra-dimension conversion between '{conv.from_unit}' and '{conv.to_unit}' "
                f"for dimension '{d_from}' in ingredient '{ingredient.id}'. "
                f"Standard universal conversions already connect all units in this dimension."
            )

        dim_pair = frozenset([d_from, d_to])
        if dim_pair in seen_dim_pairs:
            d1_fmt, d2_fmt = sorted([format_dim(d_from), format_dim(d_to)])
            raise ValueError(
                f"Double conversion across dimension pair '{d1_fmt}' <-> '{d2_fmt}' "
                f"in ingredient '{ingredient.id}' (attempted with '{conv.from_unit}' <-> '{conv.to_unit}'). "
                f"Only a single conversion edge is permitted across any pair of dimensions."
            )
        seen_dim_pairs.add(dim_pair)
