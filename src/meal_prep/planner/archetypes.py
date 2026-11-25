"""The standard archetypes per mealtime (``docs/planner.md``, "Archetypes";
meal requirements in ``planner/requirements.md``).

Lunch and dinner: a plate (protein + carb + a vegetable: cooked veg at
lunch, salad at dinner) or a one-dish meal; eating out matches takeout.
Breakfast: an oats breakfast (overnight oats + boiled eggs + flat white) or
a hot one (fried eggs, the sausage skillet or egg muffins + latte), both
strict. Snacks: apple + cottage cheese, or the clementine bowl.
"""

from __future__ import annotations

from meal_prep.enums import Mealtime, RecipeCategory
from meal_prep.planner.plan import TAKEOUT, Archetype, Role, single, split


def _of(name: str, *categories: RecipeCategory, missing: float, extra: float) -> Role:
    return Role(name, categories=frozenset(categories), missing=missing, extra=extra)


def _ids(name: str, *recipe_ids: str, missing: float, extra: float) -> Role:
    return Role(name, recipe_ids=frozenset(recipe_ids), missing=missing, extra=extra)


# Missing / extra points per dish (docs/planner.md, starting weights).
_PROTEIN = _of("protein", RecipeCategory.MODULAR_PROTEIN, missing=5, extra=3)
_CARB = _of("carb", RecipeCategory.MODULAR_CARB, missing=5, extra=3)
_COOKED_VEG = _of("veg", RecipeCategory.MODULAR_COOKED_VEG, missing=3, extra=1)
_SALAD = _of("salad", RecipeCategory.FRESH_SALAD_VEG, missing=3, extra=1)
_ONE_DISH = _of("one dish", RecipeCategory.ONE_DISH, missing=5, extra=3)

# Takeout is never planned; this archetype only matches a takeout meal that
# is already there, so the planner doesn't build a plate around it.
EAT_OUT = Archetype(
    "eat out", (_ids("takeout", TAKEOUT, missing=5, extra=1),), plannable=False
)

_STRICT = 5.0  # a breakfast is eaten as it comes: high missing and extra

STANDARD: dict[Mealtime, tuple[Archetype, ...]] = {
    Mealtime.BREAKFAST: (
        split(
            "oats breakfast",
            _ids(
                "oats",
                "blueberry-peanut-butter-overnight-oats",
                "granny-smith-maple-walnut-overnight-oats",
                "orange-cranberry-almond-overnight-oats",
                missing=_STRICT,
                extra=_STRICT,
            ),
            _ids("eggs", "boiled-eggs-with-mayo", missing=_STRICT, extra=_STRICT),
            _ids("coffee", "flat-white", missing=_STRICT, extra=_STRICT),
        ),
        split(
            "hot breakfast",
            _ids(
                "main",
                "fried-eggs-ham-toast",
                "sausage-peas-breakfast",
                "spinach-sun-dried-tomato-feta-egg-muffins",
                missing=_STRICT,
                extra=_STRICT,
            ),
            _ids("coffee", "homemade-latte", missing=_STRICT, extra=_STRICT),
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
            "apple and cottage cheese",
            _ids("apple", "honeycrisp-apple", missing=1, extra=0.5),
            _ids("cottage cheese", "cottage-cheese-snack-bowl", missing=1, extra=0.5),
        ),
        single(
            "clementine bowl",
            _ids("bowl", "cottage-cheese-clementine-bowl", missing=1, extra=0.5),
        ),
        EAT_OUT,
    ),
}
