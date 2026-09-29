"""Recipe enrichment service.

Turns an authored recipe DTO into the frozen, fully-resolved ``Recipe`` value.
Ingredients are resolved against the enriched catalog (gram conversions come
from each ingredient's own conversion graph), duplicate references are merged
to grams, body ``#cookware`` tokens are resolved to display names via the
equipment registry, and the batch/per-serving aggregates are pre-computed —
all raw and unrounded.

Equipment is authored exactly once — as ``#cookware`` tokens in the body — and
resolved here against canonical ids *and* aliases. There is no frontmatter
``equipment`` list to drift out of sync with the body.

Recipe validation is deliberately trivial here: ingredient enrichment already
guarantees gram reachability for every registered unit, so this service only
checks that a recipe references existing ingredients with registered units and
known cookware.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import TypedDict

from meal_prep.dtos.equipment import EquipmentItem
from meal_prep.dtos.recipe import RecipeDTO
from meal_prep.engines.conversion_graph import ConversionError
from meal_prep.models.ingredient import Ingredient
from meal_prep.models.recipe import Recipe, RecipeIngredient


class _MergedEntry(TypedDict):
    display_unit: str
    display_canonical: str
    display_qty: float
    grams: float


def prepare_recipe(
    recipe: RecipeDTO,
    catalog: Mapping[str, Ingredient],
    equipment: list[EquipmentItem],
) -> Recipe:
    """Resolve and validate one authored recipe into its frozen enriched value."""
    # Resolve body ``#cookware`` tokens — the single source of truth for
    # equipment. A token may be a canonical id *or* an alias (e.g. ``#pan`` ->
    # the ``skillet`` item); resolve it through both. The parser has already
    # deduped tokens and preserved first-appearance order, so this yields the
    # display-name list for the equipment panel and the raw-token -> name map
    # for the renderer's badges.
    name_by_alias: dict[str, str] = {}
    for item in equipment:
        name_by_alias[item.id] = item.name
        for alias in item.aliases:
            name_by_alias.setdefault(alias, item.name)

    resolved_equipment: list[str] = []
    cookware_by_token: dict[str, str] = {}
    for cw_ref in recipe.cookware:
        token = cw_ref.id
        name = name_by_alias.get(token)
        if name is None:
            raise ValueError(
                f"Recipe '{recipe.id}' references unknown cookware '{token}' in "
                f"the instructions body (not a known equipment id or alias)."
            )
        cookware_by_token.setdefault(token, name)
        if name not in resolved_equipment:
            resolved_equipment.append(name)

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

    merged: dict[str, _MergedEntry] = {}
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
            ) from None

        try:
            grams = ingredient.convert(ref.quantity, canonical, "g")
        except ConversionError:
            raise ValueError(
                f"Recipe '{recipe.id}' references ingredient '{ref.id}' "
                f"with unit '{unit}' that has no gram conversion "
                f"(author a '{canonical} -> g' edge on the ingredient)."
            ) from None
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
                aisle_name=ingredient.aisle_name,
                aisle_order=ingredient.aisle_order,
                storage=ingredient.storage,
                shelf_life_days=ingredient.shelf_life_days,
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
        cookware_by_token=MappingProxyType(cookware_by_token),
        ingredients=tuple(resolved_ingredients),
        instructions=recipe.instructions,
        source_path=recipe.source_path,
    )
