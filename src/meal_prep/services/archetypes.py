"""Resolve the authored archetypes against the recipes.

Checks what the file's shape can't: every named recipe exists, every role
finds at least one recipe, and no recipe fits two roles of one archetype
(a dish must have one place in a meal).
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from meal_prep.dtos.archetypes import ArchetypeDTO, ArchetypesDTO, RoleDTO
from meal_prep.enums import Mealtime
from meal_prep.models.archetype import TAKEOUT, Archetype, Role
from meal_prep.models.recipe import Recipe


def prepare_archetypes(
    dto: ArchetypesDTO, recipes: Mapping[str, Recipe]
) -> Mapping[Mealtime, tuple[Archetype, ...]]:
    """The archetypes per mealtime, validated against ``recipes``."""
    return MappingProxyType(
        {
            mealtime: tuple(
                _archetype(a, recipes, mealtime) for a in getattr(dto, mealtime.value)
            )
            for mealtime in Mealtime
        }
    )


def _archetype(
    dto: ArchetypeDTO, recipes: Mapping[str, Recipe], mealtime: Mealtime
) -> Archetype:
    where = f"archetype '{dto.name}' ({mealtime.value})"
    roles = tuple(_role(r, recipes, where) for r in dto.roles)
    for recipe in recipes.values():
        fits = [r.name for r in roles if r.accepts(recipe.id, recipe.category)]
        if len(fits) > 1:
            raise ValueError(
                f"{where}: recipe '{recipe.id}' fits roles {', '.join(fits)}; "
                "a dish may fit one role only"
            )
    return Archetype(
        dto.name,
        roles,
        base_cost=dto.base_cost,
        unknown=dto.unknown,
        plannable=dto.plannable,
    )


def _role(dto: RoleDTO, recipes: Mapping[str, Recipe], where: str) -> Role:
    unknown = sorted(set(dto.recipes) - set(recipes))
    if unknown:
        raise ValueError(
            f"{where}, role '{dto.name}': unknown recipe(s) {', '.join(unknown)}"
        )
    role = Role(
        dto.name,
        categories=frozenset(dto.categories),
        recipe_ids=frozenset(dto.recipes) | ({TAKEOUT} if dto.takeout else set()),
        count=dto.count,
        missing=dto.missing,
        extra=dto.extra,
    )
    if not dto.takeout and not any(
        role.accepts(r.id, r.category) for r in recipes.values()
    ):
        raise ValueError(f"{where}, role '{dto.name}': no recipe fits it")
    return role
