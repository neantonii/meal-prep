"""Ingredient enrichment service.

Turns an authored ingredient DTO into the frozen, fully-resolved ``Ingredient``
value. This is the only place that resolves collaborators — the units taxonomy
(default synonyms) and the conversion graph — before construction, so the
resulting model carries no hidden state and needs no registry at call time.

Pipeline
--------
1. Build the complete synonym map: default nouns from ``units.yaml`` plus the
   ingredient's ``custom_units``, rejecting overlap across any two nouns.
2. Resolve every authored conversion endpoint to its canonical unit (both
   standard and custom alike), appending universal physics edges from
   ``units.yaml``.
3. Feed the resolved edges to ``build_graph``, which enforces the structural
   invariants (no self-loops, no duplicate/reverse edges, no cycles) and returns
   the frozen transitive closure.
4. Validate gram reachability (``package``, every custom unit, the macros basis)
   and compute the derived per-100g macros and pricing — all raw, unrounded.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from meal_prep.dtos.aisle import Aisle
from meal_prep.dtos.ingredient import IngredientDTO
from meal_prep.dtos.units import UnitsFileSchema
from meal_prep.engines.conversion_graph import ConversionEdge, build_graph
from meal_prep.models.ingredient import Ingredient, MacrosInfo


def _default_synonyms(units: UnitsFileSchema) -> dict[str, str]:
    """Every registered noun (canonical + aliases) -> canonical, across all dimensions."""
    synonyms: dict[str, str] = {}
    for group in (units.mass, units.volume, units.package, units.count):
        for canonical, aliases in group.allowed.items():
            synonyms[canonical] = canonical
            for alias in aliases:
                synonyms[alias] = canonical
    return synonyms


def _universal_edges(units: UnitsFileSchema) -> list[ConversionEdge]:
    """Universal physics edges (mass -> g, volume -> ml); ``package``/``count`` have none."""
    edges: list[ConversionEdge] = []
    for group in (units.mass, units.volume, units.package, units.count):
        for canonical, step in group.conversions.items():
            edges.append(ConversionEdge(canonical, step.unit, step.amount))
    return edges


def prepare_ingredient(
    dto: IngredientDTO,
    units: UnitsFileSchema,
    aisles: Mapping[str, Aisle],
) -> Ingredient:
    """Resolve and validate one ingredient into its frozen enriched value."""
    aisle = aisles.get(dto.aisle)
    if aisle is None:
        raise ValueError(f"Ingredient '{dto.id}' declares unknown aisle '{dto.aisle}'.")

    synonyms = _default_synonyms(units)

    # Register custom units, rejecting overlap with any already-registered noun
    # (default or an earlier custom unit).
    for canonical, aliases in dto.custom_units.items():
        for noun in dict.fromkeys([canonical, *aliases]):
            if noun in synonyms:
                raise ValueError(
                    f"Ingredient '{dto.id}' custom unit noun '{noun}' (from '{canonical}') "
                    f"collides with an already-registered unit noun."
                )
            synonyms[noun] = canonical

    def resolve(token: str, *, context: str) -> str:
        if token not in synonyms:
            raise ValueError(
                f"Ingredient '{dto.id}' {context} references unregistered unit '{token}'."
            )
        return synonyms[token]

    edges: list[ConversionEdge] = _universal_edges(units)
    for conv in dto.conversions:
        src = resolve(conv.from_unit, context="conversion")
        dst = resolve(conv.to_unit, context="conversion")
        edges.append(ConversionEdge(src, dst, conv.factor))

    graph = build_graph(edges)

    def require_factor(source: str, target: str, *, what: str) -> float:
        factor = graph.factor(source, target)
        if factor is None:
            raise ValueError(
                f"Ingredient '{dto.id}' {what}: no conversion path from "
                f"'{source}' to '{target}'."
            )
        return factor

    package_weight_g = require_factor("package", "g", what="package weight")
    for canonical in dto.custom_units:
        require_factor(canonical, "g", what=f"custom unit '{canonical}'")

    # Scale macros from the authored basis to a per-100g standard.
    basis_unit = resolve(dto.macros.unit, context="macros basis")
    basis_g = graph.convert(dto.macros.amount, basis_unit, "g")
    scale = 100.0 / basis_g

    m = dto.macros
    macros = MacrosInfo(
        calories_kcal=m.calories_kcal * scale,
        protein_g=m.protein_g * scale,
        fat_g=m.fat_g * scale,
        carbs_g=m.carbs_g * scale,
        fiber_g=m.fiber_g * scale,
        saturated_fat_g=(m.saturated_fat_g or 0.0) * scale,
        sugars_g=(m.sugars_g or 0.0) * scale,
        sodium_mg=(m.sodium_mg or 0.0) * scale,
        potassium_mg=(m.potassium_mg or 0.0) * scale,
    )

    return Ingredient(
        id=dto.id,
        name=dto.name,
        step_name=dto.step_name,
        aisle_name=aisle.name,
        aisle_order=aisle.order,
        storage=dto.storage,
        shelf_life_days=dto.shelf_life_days,
        brand=dto.reference.brand,
        product=dto.reference.product,
        price=dto.reference.price,
        macros_per_100g=macros,
        custom_units=frozenset(dto.custom_units),
        synonyms=MappingProxyType(dict(synonyms)),
        conversion_graph=graph,
        package_weight_g=package_weight_g,
        price_per_100g=dto.reference.price / package_weight_g * 100.0,
    )


def prepare_catalog(
    dtos: Mapping[str, IngredientDTO],
    units: UnitsFileSchema,
    aisles: Mapping[str, Aisle],
) -> dict[str, Ingredient]:
    """Enrich every authored ingredient, keyed by id."""
    return {
        ing_id: prepare_ingredient(dto, units, aisles) for ing_id, dto in dtos.items()
    }
