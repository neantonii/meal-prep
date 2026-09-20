"""Ingredient conversion graph engine.

Constructs and precomputes the transitive closure of all possible unit transformations
for an ingredient at load time, combining invariant physics (mass and volume) with
ingredient-specific bridges (density, discrete piece mass, and packaging).
"""

from collections import deque
from typing import TYPE_CHECKING
from meal_prep.models.units import UnitsRegistry

if TYPE_CHECKING:
    from meal_prep.models.ingredient import Ingredient


class ConversionGraph:
    """Precomputed conversion map for an ingredient with O(1) factor lookups."""

    def __init__(
        self,
        ingredient_id: str,
        conversion_map: dict[tuple[str, str], float],
        units_reg: UnitsRegistry,
    ):
        self.ingredient_id = ingredient_id
        self._map = conversion_map
        self._units_reg = units_reg

    def normalize(self, unit_name: str) -> str:
        """Normalize a unit name or container noun using units registry and plural stripping."""
        clean = unit_name.strip().lower()
        if self._units_reg.is_valid_unit(clean):
            return self._units_reg.normalize(clean)

        # Handle container nouns or singular/plural fallbacks
        containers = [c.lower() for c in self._units_reg.schema_data.packaging_containers]
        if clean in containers:
            return clean
        if clean.endswith("s") and clean[:-1] in containers:
            return clean[:-1]

        return clean

    def can_convert(self, from_unit: str, to_unit: str) -> bool:
        """Return True if a conversion path exists between from_unit and to_unit."""
        u_from = self.normalize(from_unit)
        u_to = self.normalize(to_unit)
        return (u_from, u_to) in self._map

    def get_factor(self, from_unit: str, to_unit: str) -> float | None:
        """Return the multiplication factor from from_unit to to_unit, or None."""
        u_from = self.normalize(from_unit)
        u_to = self.normalize(to_unit)
        return self._map.get((u_from, u_to))

    def convert(self, amount: float, from_unit: str, to_unit: str) -> float:
        """Convert amount from from_unit to to_unit.
        
        Raises ValueError if no conversion path exists for this ingredient.
        """
        u_from = self.normalize(from_unit)
        u_to = self.normalize(to_unit)
        factor = self._map.get((u_from, u_to))
        if factor is None:
            raise ValueError(
                f"Cannot convert '{from_unit}' to '{to_unit}' for ingredient '{self.ingredient_id}'. "
                f"No conversion path exists between these units."
            )
        return round(amount * factor, 6)

    def reachable_units_from(self, from_unit: str) -> set[str]:
        """Return all units that can be reached from from_unit."""
        u_from = self.normalize(from_unit)
        return {to_u for (f_u, to_u) in self._map.keys() if f_u == u_from}

    def all_units(self) -> set[str]:
        """Return all unique unit names known to this conversion graph."""
        units = set()
        for u1, u2 in self._map.keys():
            units.add(u1)
            units.add(u2)
        return units

    @property
    def conversion_map(self) -> dict[tuple[str, str], float]:
        """Return the complete dictionary mapping (from_unit, to_unit) -> factor."""
        return self._map


def build_conversion_graph(
    ingredient: "Ingredient",
    units: UnitsRegistry,
) -> ConversionGraph:
    """Build the precomputed conversion graph for a given ingredient and units registry.
    
    Args:
        ingredient: Ingredient instance with package and conversions defined.
        units: UnitsRegistry containing standard invariant mass and volume units.

    Returns:
        ConversionGraph ready for O(1) lookups and conversions.
    """
    adjacency: dict[str, dict[str, float]] = {}

    def add_edge(u: str, v: str, factor: float) -> None:
        """Add directed edge: 1 u = factor * v (and reciprocal 1 v = (1 / factor) * u)."""
        if factor <= 0:
            return
        u_clean = u.strip().lower()
        v_clean = v.strip().lower()

        if u_clean not in adjacency:
            adjacency[u_clean] = {}
        if v_clean not in adjacency:
            adjacency[v_clean] = {}

        adjacency[u_clean][v_clean] = factor
        adjacency[v_clean][u_clean] = 1.0 / factor

    # 1. Invariant Mass conversions (base = 'g')
    mass_group = units.schema_data.mass
    for canonical in mass_group.canonical_units:
        if canonical != "g":
            factor_to_g, _ = units.to_base(1.0, canonical)
            add_edge(canonical, "g", factor_to_g)

    # 2. Invariant Volume conversions (base = 'ml')
    volume_group = units.schema_data.volume
    for canonical in volume_group.canonical_units:
        if canonical != "ml":
            factor_to_ml, _ = units.to_base(1.0, canonical)
            add_edge(canonical, "ml", factor_to_ml)

    # 3. Ingredient conversions (bridge to 'g')
    for conv in ingredient.conversions:
        unit_canonical = conv.unit.strip().lower()
        if units.is_valid_unit(unit_canonical):
            unit_canonical = units.normalize(unit_canonical)
        add_edge(unit_canonical, "g", conv.g)

    # 4. Packaging container conversions
    pkg = ingredient.package
    container = pkg.container.strip().lower()
    pkg_unit = pkg.unit.strip().lower()
    if units.is_valid_unit(pkg_unit):
        pkg_unit = units.normalize(pkg_unit)

    # Container to grams net weight
    add_edge(container, "g", pkg.container_weight_g)
    # Container to discrete unit count
    add_edge(container, pkg_unit, pkg.amount)

    # Precompute all reachable pairs using BFS (shortest path = minimal precision drift)
    conversion_map: dict[tuple[str, str], float] = {}
    for source in adjacency:
        visited = {source: 1.0}
        queue = deque([source])
        while queue:
            curr = queue.popleft()
            curr_factor = visited[curr]
            for neighbor, edge_factor in adjacency[curr].items():
                if neighbor not in visited:
                    visited[neighbor] = curr_factor * edge_factor
                    queue.append(neighbor)

        for target, factor in visited.items():
            conversion_map[(source, target)] = factor

    return ConversionGraph(
        ingredient_id=ingredient.id,
        conversion_map=conversion_map,
        units_reg=units,
    )
