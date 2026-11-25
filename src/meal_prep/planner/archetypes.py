"""The standard archetypes per mealtime (``docs/planner.md``, "Archetypes";
meal requirements in ``planner/requirements.md``).

Lunch and dinner: a plate (protein + carb + a vegetable: cooked veg at
lunch, salad at dinner) or a one-dish meal; eating out matches takeout.
Breakfast: an oats breakfast (overnight oats + boiled eggs + coffee) or a
hot one (a hot main + coffee), both strict. Snacks: fruit + a snack bowl,
or a fruit bowl.

Pools are recipe categories or meal roles, never recipe ids: a recipe
says which role it plays in its own file (``meal_role``), so a new
breakfast needs no change here.
"""

from __future__ import annotations

from meal_prep.enums import MealRole, Mealtime, RecipeCategory
from meal_prep.planner.plan import Archetype, Role, single, split


def _of(name: str, *categories: RecipeCategory, missing: float, extra: float) -> Role:
    return Role(name, categories=frozenset(categories), missing=missing, extra=extra)


def _playing(name: str, *roles: MealRole, missing: float, extra: float) -> Role:
    return Role(name, meal_roles=frozenset(roles), missing=missing, extra=extra)


# Missing / extra points per dish (docs/planner.md, starting weights).
_PROTEIN = _of("protein", RecipeCategory.MODULAR_PROTEIN, missing=5, extra=3)
_CARB = _of("carb", RecipeCategory.MODULAR_CARB, missing=5, extra=3)
_COOKED_VEG = _of("veg", RecipeCategory.MODULAR_COOKED_VEG, missing=3, extra=1)
_SALAD = _of("salad", RecipeCategory.FRESH_SALAD_VEG, missing=3, extra=1)
_ONE_DISH = _of("one dish", RecipeCategory.ONE_DISH, missing=5, extra=3)

# Takeout is never planned; this archetype only matches a takeout meal that
# is already there, so the planner doesn't build a plate around it.
EAT_OUT = Archetype(
    "eat out", (Role("takeout", takeout=True, missing=5, extra=1),), plannable=False
)

_STRICT = 5.0  # a breakfast is eaten as it comes: high missing and extra
_COFFEE = _playing("coffee", MealRole.COFFEE, missing=_STRICT, extra=_STRICT)

STANDARD: dict[Mealtime, tuple[Archetype, ...]] = {
    Mealtime.BREAKFAST: (
        split(
            "oats breakfast",
            _playing("oats", MealRole.OVERNIGHT_OATS, missing=_STRICT, extra=_STRICT),
            _playing("eggs", MealRole.BOILED_EGGS, missing=_STRICT, extra=_STRICT),
            _COFFEE,
        ),
        split(
            "hot breakfast",
            _playing("main", MealRole.HOT_BREAKFAST, missing=_STRICT, extra=_STRICT),
            _COFFEE,
        ),
    ),
    Mealtime.LUNCH: (
        split("plate", _PROTEIN, _CARB, _COOKED_VEG),
        single("one dish", _ONE_DISH, base_cost=0.5),
        EAT_OUT,
    ),
    Mealtime.DINNER: (
        split("plate", _PROTEIN, _CARB, _SALAD),
        single("one dish", _ONE_DISH, base_cost=0.5),
        EAT_OUT,
    ),
    Mealtime.SNACKS: (
        split(
            "fruit and snack bowl",
            _playing("fruit", MealRole.FRUIT, missing=1, extra=0.5),
            _playing("snack bowl", MealRole.SNACK_BOWL, missing=1, extra=0.5),
        ),
        single(
            "fruit bowl", _playing("bowl", MealRole.FRUIT_BOWL, missing=1, extra=0.5)
        ),
        EAT_OUT,
    ),
}
