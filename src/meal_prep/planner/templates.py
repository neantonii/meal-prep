"""The standard meal pattern as templates (``planner/requirements.md``).

Breakfast is one of the fixed sets (B1, B2); lunch and dinner are a modular
protein, a carb and a vegetable (cooked veg at lunch, fresh salad at
dinner), or one one-dish meal (L1, D1); snacks are an apple and cottage
cheese, plus any other snack.
"""

from __future__ import annotations

from meal_prep.enums import Mealtime, RecipeCategory
from meal_prep.planner.plan import MealTemplate, Option, Role


def _fixed(name: str, *recipe_ids: str) -> Option:
    """A breakfast eaten as a whole: one role per recipe."""
    return Option(
        name=name,
        roles=tuple(Role(rid, recipe_ids=frozenset({rid})) for rid in recipe_ids),
    )


def _category(name: str, category: RecipeCategory) -> Role:
    return Role(name, categories=frozenset({category}))


_PROTEIN = _category("protein", RecipeCategory.MODULAR_PROTEIN)
_CARB = _category("carb", RecipeCategory.MODULAR_CARB)
_ONE_DISH = Option("one dish", (_category("one dish", RecipeCategory.ONE_DISH),))

STANDARD: dict[Mealtime, MealTemplate] = {
    Mealtime.BREAKFAST: MealTemplate(
        options=(
            _fixed(
                "oats",
                "blueberry-peanut-butter-overnight-oats",
                "boiled-eggs-with-mayo",
                "flat-white",
            ),
            _fixed("fried eggs", "fried-eggs-ham-toast", "homemade-latte"),
            _fixed("sausage and peas", "sausage-peas-breakfast", "homemade-latte"),
        )
    ),
    Mealtime.LUNCH: MealTemplate(
        options=(
            Option(
                "plate",
                (
                    _PROTEIN,
                    _CARB,
                    _category("cooked veg", RecipeCategory.MODULAR_COOKED_VEG),
                ),
            ),
            _ONE_DISH,
        )
    ),
    Mealtime.DINNER: MealTemplate(
        options=(
            Option(
                "plate",
                (
                    _PROTEIN,
                    _CARB,
                    _category("salad", RecipeCategory.FRESH_SALAD_VEG),
                ),
            ),
            _ONE_DISH,
        )
    ),
    Mealtime.SNACKS: MealTemplate(
        options=(
            _fixed(
                "apple and cottage cheese",
                "honeycrisp-apple",
                "cottage-cheese-snack-bowl",
            ),
        ),
        extras=_category("snack", RecipeCategory.SNACKS),
    ),
}
