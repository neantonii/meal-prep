# Meal Plan Requirements

Week-agnostic. Drafted together, section by section.

## General

- G1: Maximize variety across the week, bounded by batch-cooking reality: if a
  recipe yields N portions, all N must be eaten within its `fridge_days`.
- G2: Fresh salads (1-day fridge life, except vitaminka) are made ad hoc, day-of —
  never batched ahead.

## Nutrition

- N1: ~2100 kcal/day all-in (meals + snacks), stable day to day.
- N2: Decent protein and fiber every day; overall balanced diet, no hard macro split.

## Breakfast

- B1: Oatmeal on Mon / Wed / Fri: `blueberry-peanut-butter-overnight-oats` +
  `boiled-eggs-with-mayo` + `flat-white`.
- B2: Other days rotate through `fried-eggs-ham-toast` and `sausage-peas-breakfast`,
  each paired with `homemade-latte`.

## Lunch

- L1: 1 modular protein + 1 modular carb + 1 modular cooked veg, or 1 one-dish meal.

## Dinner

- D1: 1 modular protein + 1 modular carb + 1 fresh salad, or 1 one-dish meal.

## Pairing rules

- P1: Rice-stick noodles (`boiled-rice-stick-noodles`) only pair with ground/minced
  meats (`pan-fried-ground-beef`, `pan-fried-ground-turkey`) — never with whole-cut
  protein. Other noodles/pasta (e.g. capellini) pair freely.

## Snacks

- S1 (TODO): Discretionary, unplanned for now — fills the gap between planned meals
  and the ~2100 kcal target.

## Planner

- The archetypes in `planner/archetypes.py` encode B1/B2, L1, D1 and the
  snacks; `docs/planner.md` is the design.
