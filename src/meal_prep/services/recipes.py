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
from meal_prep.engines.conversion_graph import ConversionError
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
    # occurrence"). Dict insertion order preserves first occurrence. An empty
    # unit means a count (the reserved 'count' node).
    # Count declarations per ingredient: `repeated` is true when an ingredient
    # is declared with an amount more than once (mentions are not declarations).
    decl_count: dict[str, int] = {}
    for ref in recipe.ingredients:
        decl_count[ref.id] = decl_count.get(ref.id, 0) + 1

    merged: dict[str, dict] = {}
    for ref in recipe.ingredients:
        ingredient = catalog.get(ref.id)
        if ingredient is None:
            raise ValueError(
                f"Recipe '{recipe.id}' references unknown ingredient '{ref.id}'."
            )
        unit = ref.unit or "count"
        try:
            canonical = ingredient.resolve(unit)
        except KeyError:
            raise ValueError(
                f"Recipe '{recipe.id}' references ingredient '{ref.id}' "
                f"with unknown unit '{unit}'."
            )

        try:
            grams = ingredient.convert(ref.quantity, canonical, "g")
        except ConversionError:
            raise ValueError(
                f"Recipe '{recipe.id}' references ingredient '{ref.id}' "
                f"with unit '{unit}' that has no gram conversion "
                f"(author a '{canonical} -> g' edge on the ingredient)."
            )
        entry = merged.get(ref.id)
        if entry is None:
            entry = {
                "display_unit": unit,
                "display_canonical": canonical,
                "display_qty": 0.0,
                "grams": 0.0,
            }
            merged[ref.id] = entry
        entry["display_qty"] += ingredient.convert(
            ref.quantity, canonical, entry["display_canonical"]
        )
        entry["grams"] += grams

    # Validate amount-less mentions: every mention must be backed by a
    # declaration (an ingredient with an actual amount) elsewhere in the recipe.
    for mention in recipe.mentions:
        if mention.id not in merged:
            raise ValueError(
                f"Recipe '{recipe.id}' mentions ingredient '{mention.id}' "
                f"but it has no amount declared in the instructions."
            )

    resolved_ingredients = []
    for ing_id, entry in merged.items():
        ingredient = catalog[ing_id]
        grams = entry["grams"]
        resolved_ingredients.append(
            RecipeIngredient(
                id=ing_id,
                name=ingredient.name,
                step_name=ingredient.step_name,
                quantity=entry["display_qty"],
                unit=entry["display_unit"],
                grams=grams,
                cost=ingredient.price_per_100g * grams / 100.0,
                macros=ingredient.macros_per_100g.scaled(grams / 100.0),
                repeated=decl_count[ing_id] > 1,
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
