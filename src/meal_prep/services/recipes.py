"""Recipe enrichment service.

Turns an authored recipe DTO into the frozen, fully-resolved ``Recipe`` value.
Ingredients are resolved against the enriched catalog (gram conversions come
from each ingredient's own conversion graph), duplicate references are merged
to grams, equipment IDs are resolved to display names via the equipment
registry, and the batch/per-serving aggregates are pre-computed — all raw and
unrounded.

Recipe validation is deliberately trivial here: ingredient enrichment already
guarantees gram reachability for every registered unit, so this service only
checks that a recipe references existing ingredients with registered units and
known equipment.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from meal_prep.dtos.recipe import Recipe as RecipeDTO
from meal_prep.dtos.equipment import EquipmentItem
from meal_prep.models.ingredient import Ingredient
from meal_prep.models.recipe import Recipe, RecipeIngredient


def prepare_recipe(
    recipe: RecipeDTO,
    catalog: Mapping[str, Ingredient],
    equipment: list[EquipmentItem],
) -> Recipe:
    """Resolve and validate one authored recipe into its frozen enriched value."""
    # Resolve equipment ids to display names, preserving authored order and
    # rejecting ids that are not in the registry. The id -> name map is retained
    # on the recipe so the renderer can resolve body ``#cookware`` tokens.
    names_by_id = {item.id: item.name for item in equipment}
    resolved_equipment = []
    for equip_id in recipe.equipment:
        if equip_id not in names_by_id:
            raise ValueError(
                f"Recipe '{recipe.id}' references unknown equipment '{equip_id}'."
            )
        resolved_equipment.append(names_by_id[equip_id])

    # Merge duplicate ingredient references: same id across multiple lines sums
    # to grams (canonical) for cost/macros, and also to a display amount in the
    # ingredient's first-authored unit (Cooklang's "fallback to first
    # occurrence"). Dict insertion order preserves first occurrence.
    merged: dict[str, dict] = {}
    for ref in recipe.ingredients:
        ingredient = catalog.get(ref.id)
        if ingredient is None:
            raise ValueError(
                f"Recipe '{recipe.id}' references unknown ingredient '{ref.id}'."
            )
        try:
            canonical = ingredient.resolve(ref.unit)
        except KeyError:
            raise ValueError(
                f"Recipe '{recipe.id}' references ingredient '{ref.id}' "
                f"with unknown unit '{ref.unit}'."
            )

        grams = ingredient.convert(ref.quantity, canonical, "g")
        entry = merged.get(ref.id)
        if entry is None:
            entry = {
                "display_unit": ref.unit,
                "display_canonical": canonical,
                "display_qty": 0.0,
                "grams": 0.0,
            }
            merged[ref.id] = entry
        entry["display_qty"] += ingredient.convert(
            ref.quantity, canonical, entry["display_canonical"]
        )
        entry["grams"] += grams

    resolved_ingredients = []
    for ing_id, entry in merged.items():
        ingredient = catalog[ing_id]
        grams = entry["grams"]
        resolved_ingredients.append(
            RecipeIngredient(
                id=ing_id,
                name=ingredient.name,
                quantity=entry["display_qty"],
                unit=entry["display_unit"],
                grams=grams,
                cost=ingredient.price_per_100g * grams / 100.0,
                macros=ingredient.macros_per_100g.scaled(grams / 100.0),
            )
        )

    return Recipe(
        id=recipe.id,
        title=recipe.title,
        category=recipe.category,
        servings=recipe.yield_info.servings,
        cooked_g=recipe.yield_info.cooked_g,
        fridge_days=recipe.storage_info.fridge_days,
        freezer_friendly=recipe.storage_info.freezer_friendly,
        equipment=tuple(resolved_equipment),
        equipment_by_id=MappingProxyType(names_by_id),
        ingredients=tuple(resolved_ingredients),
        instructions=recipe.instructions,
        source_path=recipe.source_path,
    )
