"""Tests for the week-plan solver (``meal_prep/planner/solver.py``).

All recipes are hand-built fakes; the cheapest assignment is known exactly.
"""

from __future__ import annotations

import datetime
import itertools

import pytest

from meal_prep.enums import Aisle, Mealtime, RecipeCategory, StorageType
from meal_prep.models.ingredient import MacrosInfo, Package
from meal_prep.models.recipe import Recipe, RecipeIngredient
from meal_prep.planner.plan import KcalGoal, MealSlot, WeekPlan
from meal_prep.planner.quadratic import ConvexQuadratic
from meal_prep.planner.solver import plan_horizon, plan_week


def _macros(*, cal: float = 100.0, protein: float = 10.0) -> MacrosInfo:
    return MacrosInfo(
        calories_kcal=cal,
        protein_g=protein,
        fat_g=5.0,
        carbs_g=20.0,
        fiber_g=1.0,
        saturated_fat_g=0.0,
        sugars_g=0.0,
        sodium_mg=0.0,
        potassium_mg=0.0,
    )


def _recipe(
    recipe_id: str,
    *,
    cost: float,
    category: RecipeCategory = RecipeCategory.MODULAR_PROTEIN,
    servings: float = 1.0,
    kcal: float = 100.0,
) -> Recipe:
    return Recipe(
        id=recipe_id,
        title=f"Recipe {recipe_id}",
        category=category,
        servings=servings,
        cooked_g=200.0,
        fridge_days=4,
        freezer_friendly=True,
        equipment=(),
        cookware_by_token={},
        ingredients=(
            RecipeIngredient(
                id="a",
                name="A",
                step_name="a",
                aisle=Aisle.MEAT,
                storage=StorageType.REFRIGERATED,
                shelf_life_days=3,
                quantity=200.0,
                unit="g",
                grams=200.0,
                cost=cost,
                macros=_macros(cal=kcal),
                package=Package("Test 1 kg", 1.0, "kg", 1000.0),
            ),
        ),
        instructions="Cook.",
    )


def test_picks_cheapest_meal_every_meal():
    plan = plan_week(
        [
            _recipe("cheap", cost=1.0, servings=2.0),
            _recipe("pricey", cost=9.0),
            _recipe("morning", cost=2.0, category=RecipeCategory.BREAKFAST),
        ]
    )
    assert isinstance(plan, WeekPlan)
    assert len(plan.days) == 7
    for day in plan.days:
        assert day.breakfast.recipe_id == "morning"
        assert day.lunch.recipe_id == "cheap"
        assert day.dinner.recipe_id == "cheap"
    # 14 cheap uses at servings=2 need exactly 7 batches (the bound edge).
    assert [(batch.recipe_id, batch.batches) for batch in plan.prep] == [
        ("cheap", 7),
        ("morning", 7),
    ]
    assert plan.total_cost == 7 * 1.0 + 7 * 2.0


def test_breakfast_comes_from_breakfast_category():
    plan = plan_week(
        [
            _recipe("oats", cost=5.0, category=RecipeCategory.BREAKFAST),
            _recipe("eggs", cost=1.0, category=RecipeCategory.BREAKFAST),
            _recipe("stew", cost=0.5, servings=2.0),
        ]
    )
    for day in plan.days:
        assert day.breakfast.recipe_id == "eggs"
        assert day.lunch.recipe_id == "stew"
        assert day.dinner.recipe_id == "stew"


def test_batch_bound_caps_cook_sessions_at_seven():
    # One servings=7 recipe: 21 uses need only 3 batches, within the bound.
    plan = plan_week(
        [_recipe("only", cost=2.5, category=RecipeCategory.BREAKFAST, servings=7.0)]
    )
    assert isinstance(plan, WeekPlan)
    assert [(batch.recipe_id, batch.batches) for batch in plan.prep] == [
        ("only", 3),
    ]
    assert plan.total_cost == 3 * 2.5


def test_big_batch_needs_fewer_batches():
    # Breakfasts are pricey so they stay out of the lunch/dinner slots.
    plan = plan_week(
        [
            _recipe("morning", cost=10.0, category=RecipeCategory.BREAKFAST),
            _recipe("tray", cost=6.0, servings=4.0),
            _recipe("pot", cost=5.0, servings=2.0),
            _recipe("single", cost=4.0, servings=1.0),
        ]
    )
    # 14 lunch/dinner uses: 3 trays cover 12 ($18) + 1 pot covers 2 ($5)
    # beats 4 trays ($24) and 7 pots ($35).
    assert [(batch.recipe_id, batch.batches) for batch in plan.prep] == [
        ("morning", 7),
        ("pot", 1),
        ("tray", 3),
    ]
    assert plan.total_cost == 7 * 10.0 + 1 * 5.0 + 3 * 6.0


def test_leftover_is_charged_at_full_batch_cost():
    plan = plan_week(
        [
            _recipe("morning", cost=10.0, category=RecipeCategory.BREAKFAST),
            _recipe("tray", cost=3.0, servings=4.0),
            _recipe("single", cost=2.0, servings=1.0),
            _recipe("other", cost=2.0, servings=1.0),
        ]
    )
    # 14 lunch/dinner uses: 4 trays make 16 ($12, 2 leftover) beats 3 trays
    # + 2 singles ($9 + $4 = $13). Leftover is tolerated but charged: the
    # tray line costs the full 4 batches.
    by_id = {batch.recipe_id: batch for batch in plan.prep}
    assert by_id["tray"].batches == 4
    assert by_id["tray"].portions_used == 14
    assert by_id["tray"].leftover == 2
    assert by_id["tray"].cost == 12.0
    assert plan.total_cost == 7 * 10.0 + 12.0


def test_rejects_empty_recipes():
    with pytest.raises(ValueError, match="at least one recipe"):
        plan_week([])


def test_rejects_missing_breakfast_recipes():
    with pytest.raises(ValueError, match="at least one breakfast recipe"):
        plan_week([_recipe("stew", cost=1.0)])


def test_many_recipes_solve():
    recipes = [_recipe(f"meal-{idx}", cost=float(idx + 1)) for idx in range(10)]
    recipes.append(_recipe("morning", cost=0.5, category=RecipeCategory.BREAKFAST))
    plan = plan_week(recipes)
    assert isinstance(plan, WeekPlan)


def _day_kcal(plan: WeekPlan) -> list[float]:
    return [day.macros.calories_kcal for day in plan.days]


def test_daily_kcal_pull_matches_brute_force():
    # One 21-serving batch covers any use pattern, so batch cost is paid
    # once per used recipe; at zero cost only the kcal penalty is left and
    # every day is independent: brute force one day.
    recipes = [
        _recipe(
            "oats",
            cost=0.0,
            category=RecipeCategory.BREAKFAST,
            servings=21.0,
            kcal=400 * 21,
        ),
        *(
            _recipe(f"meal-{kcal}", cost=0.0, servings=21.0, kcal=kcal * 21)
            for kcal in (500, 900, 1300)
        ),
    ]
    penalty = ConvexQuadratic.deviation(2050, 0.01)
    plan = plan_week(recipes, daily_kcal=penalty)

    options = (400, 500, 900, 1300)  # lunch/dinner may be any recipe
    best = min(
        (400 + a + b for a, b in itertools.product(options, repeat=2)),
        key=penalty,
    )
    assert best == 2100  # 400 + 400 + 1300
    assert _day_kcal(plan) == pytest.approx([best] * 7)


def test_daily_kcal_trades_off_against_cost():
    # Pricey hearty meals hit 2100 kcal; cheap light ones fall short. Oats
    # cover exactly the 7 breakfasts; reusing them costs a 10-euro batch.
    recipes = [
        _recipe(
            "oats",
            cost=10.0,
            category=RecipeCategory.BREAKFAST,
            servings=7.0,
            kcal=500 * 7,
        ),
        _recipe("light", cost=1.0, servings=21.0, kcal=300 * 21),
        _recipe("hearty", cost=20.0, servings=21.0, kcal=800 * 21),
    ]

    def solve(weight: float) -> list[float]:
        target = ConvexQuadratic.deviation(2100, weight)
        return _day_kcal(plan_week(recipes, daily_kcal=target))

    # Hearty costs 1900 cents more than light; light falls 1000 kcal short
    # on each of 7 days, so the shortfall costs 7 x 1000² x w cents.
    assert solve(1e-5) == pytest.approx([1100] * 7)  # 70 cents: stay light
    assert solve(1e-3) == pytest.approx([2100] * 7)  # 7000 cents: go hearty


def _day_slots(day: datetime.date) -> list[MealSlot]:
    return [MealSlot(date=day, mealtime=m, session=day) for m in Mealtime]


_THU = datetime.date(2026, 11, 5)
# 1000- and 100-kcal recipes, at most one of each per slot: any multiple of
# 100 up to 4400 kcal a day.
_KCAL_RECIPES = [_recipe("big", cost=0.0, kcal=1000), _recipe("small", cost=0.0)]


@pytest.mark.parametrize(
    ("payback", "expected"),
    [
        (0.0, 2100),  # rolling term off: hit the daily target
        # Yesterday 600 short: today makes up half -> 2400. (Window
        # 2100 + 1500 + x pays (x - 2700)², the day pays (x - 2100)².)
        (0.5, 2400),
    ],
)
def test_horizon_day_makes_up_yesterday(payback: float, expected: int):
    plan = plan_horizon(
        _KCAL_RECIPES,
        _day_slots(_THU),
        goal=KcalGoal(payback=payback),
        known_kcal={
            _THU - datetime.timedelta(days=2): 2100,
            _THU - datetime.timedelta(days=1): 1500,
        },
    )
    assert plan.day_kcal == ((_THU, pytest.approx(expected)),)


def test_horizon_counts_known_kcal_on_planned_days():
    # 1100 already logged today: the slots add the remaining 1000.
    plan = plan_horizon(
        _KCAL_RECIPES,
        _day_slots(_THU),
        goal=KcalGoal(payback=0.0),
        known_kcal={_THU: 1100},
    )
    assert plan.day_kcal == ((_THU, pytest.approx(2100)),)
    added = sum(p.meal.macros.calories_kcal for p in plan.sessions[0].picks)
    assert added == pytest.approx(1000)


def test_horizon_splits_sessions_and_flags_truncated():
    friday = _THU + datetime.timedelta(days=1)
    slots = [
        *_day_slots(_THU),
        *(MealSlot(date=friday, mealtime=m, session=friday) for m in Mealtime),
    ]
    plan = plan_horizon(
        _KCAL_RECIPES,
        slots,
        goal=KcalGoal(payback=0.0),
        known_kcal={},
        truncated={friday},
    )
    assert [(s.session, s.truncated) for s in plan.sessions] == [
        (_THU, False),
        (friday, True),
    ]
    assert all(p.slot.session == _THU for p in plan.sessions[0].picks)
