"""Week 2026-11-02 .. 08 as logged so far, against the real recipe library.

A fixed slice of history for experimenting with the planner: Mon-Wed are
logged in full, Thu has breakfast and lunch, Fri-Sun are still to plan.
Each slot lists recipe ids, one serving each.

Expected day totals are the diary UI's (kcal, protein, carbs, fat). The
library reproduces them except Braised Cabbage: the diary still shows the
old 3-serving portion (112 kcal), the recipe is now 2 servings (117 kcal),
hence the kcal tolerance.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from meal_prep.enums import RecipeCategory
from meal_prep.library import load_library
from meal_prep.models.library import Library

_REPO_ROOT = Path(__file__).resolve().parents[3]

Slot = tuple[str, ...]
Day = dict[str, Slot]

HISTORY: dict[str, Day] = {
    "Mon": {
        "breakfast": (
            "blueberry-peanut-butter-overnight-oats",
            "boiled-eggs-with-mayo",
            "flat-white",
        ),
        "lunch": (
            "pan-fried-ground-beef",
            "boiled-rice-stick-noodles",
            "skillet-blistered-cauliflower-florets",
        ),
        "dinner": (
            "soy-ginger-sesame-shrimp",
            "boiled-basmati-rice",
            "radish-scallion-yogurt-salad",
        ),
        "snacks": ("cottage-cheese-snack-bowl",),
    },
    "Tue": {
        "breakfast": ("fried-eggs-ham-toast", "homemade-latte"),
        "lunch": (
            "air-fried-chicken-breast",
            "avocado-oil-mashed-potatoes",
            "skillet-blistered-cauliflower-florets",
        ),
        "dinner": (
            "crispy-garlic-soy-glazed-tofu",
            "mediterranean-garden-salad-lemon-dijon",
            "boiled-basmati-rice",
        ),
        "snacks": ("cottage-cheese-snack-bowl", "honeycrisp-apple"),
    },
    "Wed": {
        "breakfast": (
            "blueberry-peanut-butter-overnight-oats",
            "boiled-eggs-with-mayo",
            "flat-white",
        ),
        "lunch": (
            "pan-fried-ground-beef",
            "boiled-roasted-buckwheat",
            "braised-cabbage-tomato-aromatics",
        ),
        "dinner": (
            "spiced-butter-glazed-wild-pollock",
            "sweet-corn-and-green-peas",
            "vitaminka-cabbage-carrot-salad",
        ),
        "snacks": ("cottage-cheese-snack-bowl", "honeycrisp-apple"),
    },
    "Thu": {
        "breakfast": ("fried-eggs-ham-toast", "homemade-latte"),
        "lunch": (
            "crispy-garlic-soy-glazed-tofu",
            "boiled-basmati-rice",
            "braised-cabbage-tomato-aromatics",
        ),
        "dinner": (),
        "snacks": (),
    },
    "Fri": {"breakfast": (), "lunch": (), "dinner": (), "snacks": ()},
    "Sat": {"breakfast": (), "lunch": (), "dinner": (), "snacks": ()},
    "Sun": {"breakfast": (), "lunch": (), "dinner": (), "snacks": ()},
}

# Diary UI day totals: kcal, protein g, carbs g, fat g.
UI_TOTALS: dict[str, tuple[float, float, float, float]] = {
    "Mon": (2008, 159, 198, 65),
    "Tue": (2077, 163, 198, 76),
    "Wed": (2216, 168, 228, 78),
    "Thu": (1266, 84, 115, 54),
    "Fri": (0, 0, 0, 0),
    "Sat": (0, 0, 0, 0),
    "Sun": (0, 0, 0, 0),
}

# Requirements L1 / D1: which categories make up a full lunch and dinner.
LUNCH = {
    RecipeCategory.MODULAR_PROTEIN,
    RecipeCategory.MODULAR_CARB,
    RecipeCategory.MODULAR_COOKED_VEG,
}
DINNER = {
    RecipeCategory.MODULAR_PROTEIN,
    RecipeCategory.MODULAR_CARB,
    RecipeCategory.FRESH_SALAD_VEG,
}


@pytest.fixture(scope="module")
def library() -> Library:
    return load_library(_REPO_ROOT / "data", _REPO_ROOT / "recipes")


def _day_totals(library: Library, day: Day) -> tuple[float, float, float, float]:
    macros = [
        library.recipes[recipe_id].per_serving_macros
        for slot in day.values()
        for recipe_id in slot
    ]
    return (
        sum(m.calories_kcal for m in macros),
        sum(m.protein_g for m in macros),
        sum(m.carbs_g for m in macros),
        sum(m.fat_g for m in macros),
    )


def test_every_logged_recipe_exists(library: Library):
    missing = {
        recipe_id
        for day in HISTORY.values()
        for slot in day.values()
        for recipe_id in slot
        if recipe_id not in library.recipes
    }
    assert not missing


@pytest.mark.parametrize("day_name", list(HISTORY))
def test_day_totals_match_the_diary(library: Library, day_name: str):
    kcal, protein, carbs, fat = _day_totals(library, HISTORY[day_name])
    ui_kcal, ui_protein, ui_carbs, ui_fat = UI_TOTALS[day_name]
    assert kcal == pytest.approx(ui_kcal, abs=6)  # cabbage: 117 now, 112 logged
    assert protein == pytest.approx(ui_protein, abs=1)
    assert carbs == pytest.approx(ui_carbs, abs=1)
    assert fat == pytest.approx(ui_fat, abs=1)


def test_week_total_matches_the_diary(library: Library):
    kcal = sum(_day_totals(library, day)[0] for day in HISTORY.values())
    assert kcal == pytest.approx(7568, abs=10)


@pytest.mark.parametrize(("slot", "categories"), [("lunch", LUNCH), ("dinner", DINNER)])
def test_full_meals_follow_the_templates(
    library: Library, slot: str, categories: set[RecipeCategory]
):
    for day in HISTORY.values():
        if not day[slot]:
            continue
        logged = sorted(library.recipes[r].category.value for r in day[slot])
        assert logged == sorted(c.value for c in categories)
