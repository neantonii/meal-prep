# Planner

Status: design. Building blocks exist (the quadratic helper,
`planner/quadratic.py`); the app integration below is not built. The
model and the terms were tried in a sandbox (branch
`sandbox/session-optimizer`, kept for reference only). The meal
requirements themselves (what a breakfast is, the kcal target, pairing
rules) are in `src/meal_prep/planner/requirements.md`.

## Goal

Press one button and get a week of meals and the prep sessions that cook
them, written into the diary like hand-placed meals. The plan only has to
be half useful: anything wrong is fixed by hand with the existing editing,
and the model is tuned step by step on real data.

## How it fits the app

The planner fills diary slots the same way a person does
(`docs/prep-sessions.md`, `docs/freezer.md`): every portion is a meal, a
batch is exactly its portions, and leftovers go to the unassigned slot.

- **Plan** (one button, on the week page) plans the **week ahead**: every
  empty slot from the next planned session's cycle through the horizon
  (below). It writes all of it: sessions with batch counts, meals on days,
  leftover portions unassigned. Slots that already hold something (manual
  meals, takeout, accepted meals) are left alone and count as fixed.
- **Planned meals are flagged.** Every meal the planner creates, on a day or
  unassigned, carries `planned: true` (an optional entry field; existing
  files load unchanged). The week page shows them with a distinct style.
- **Accept** (on a session): its planned meals become manual (the flag is
  cleared). Moving a planned meal by hand also makes it manual.
- **Clear plans** (one global button): removes every planned meal of every
  planned session, and the batches only they needed (each recipe keeps
  enough batches for its remaining manual meals; spare portions of a kept
  batch go to the unassigned slot). Cooked sessions are not touched.
- **Retry** is Clear plans, then Plan. The planner is deterministic, so the
  same inputs give the same plan; a random seed is a later option.
- **Inputs it reads:** the library (recipes), the diary (meals already on
  days, takeout, the unassigned slot as stock), today, and the config
  (below).

OR-Tools moves into the server image for this (it was kept out to save
about 225 MB).

## The model

### Slots and templates

Every mealtime of every day in the horizon is a slot. A **template** per
mealtime says what a slot holds (requirements B1/B2, L1, D1, S1):

- **roles:** each filled by exactly one recipe from a category or a list
  (lunch: protein + carb + cooked veg);
- **presets:** alternatively one fixed set of recipes eaten whole (the two
  breakfasts);
- **alternatives:** a whole other shape (lunch or dinner: one one-dish
  recipe instead of the three roles);
- **extras:** optional additions (snacks: any other snack; the escape
  hatch).

Nothing else goes in a slot. Templates start strict (hard rules) and can
be softened later into penalties for leaving the pattern.

### Sessions and batches

Sessions are on the preset days (Sun, Tue, Thu). A meal belongs to the
session on its cycle day (`cycle_day`). For each session and recipe, the
batch count is a decision: `uses ≤ batches × servings`, and the portions
not placed on a day are leftovers (unassigned).

### Horizon

The planner looks ahead by **calendar days**, not by sessions, so every day
it plans is complete (kcal and per-day rules never see half a day). With
the default of 7 days, the last session in the horizon is usually cut off
part-way (its cycle runs past the last day): its batch numbers are rough,
so penalties that only make sense for a whole cycle (leftovers, waste) are
relaxed for it. The cut is far from the first sessions, and a 3-day window
cannot reach that far. Check: a 7-day and a 14-day horizon should give the
same plan for the first sessions.

Rejected: a horizon in whole sessions (the last day comes out half
planned), and averaging kcal over shifted "dinner-to-lunch" days (every
per-day rule would have to pick a kind of day).

### Fixed inputs

- Meals already on days (manual, takeout, accepted) count as fixed: their
  kcal enter the day and window sums, their recipes enter the repeat
  terms.
- Days before the horizon (logged history) count as fixed numbers in the
  rolling windows and repeat terms.
- Unassigned portions are free stock (planned use: later).

## Point system

Every soft term is in **points**, so unlike terms can be weighed against
each other. A term has one of two shapes:

- **Amount:** `weight × ((x − target) / tolerance)²`. One point means one
  tolerance off. Built with the quadratic helper (secant cuts on `x²`).
- **Event:** `weight × count`. One point per unwanted event.

Weights start at 1 and are tuned by looking at real plans. Every plan
reports its points per term, so a strange plan can be explained.

## Terms

| Term | Shape | Parameters | Status |
|---|---|---|---|
| Templates | hard | per mealtime | first version |
| No recipe twice in a day | hard | | first version |
| Leftover portion | event | 1 point each | first version |
| Repeat on the next day | event | 1 point each | first version |
| Daily kcal | amount | 2100, tolerance 100, hard 0–4000 | next |
| Rolling kcal | amount | 3-day window, payback 0.5 | next |
| Repeat in the next session | event | 2 points each | next |
| Long-run frequency | amount | equal shares per role, 14-day half-life | later |
| Freshness | amount | per recipe, from `fridge_days` | later |
| Protein and carb spread | amount | over breakfast, lunch, dinner | later |

Notes per term:

- **Rolling kcal.** Each day pays `(kcal − 2100)²`; each 3-day run pays
  `w · (sum − 6300)²` with `w = payback / (1 − payback)`. `payback` is the
  share of one day's miss the next day makes up when it is the only free
  day in its window (0.5: half). Without the daily term a window allows
  0, 4200, 0, 4200, so both are needed.
- **Repeats.** A day in between costs nothing (Mon and Wed is fine). With
  the same-day rule a recipe is used at most once a day, so a repeat is a
  flag `≥ used(d) + used(d+1) − 1`. Sessions: the same with "the session
  uses the recipe".
- **Long-run frequency.** Weighted counts decay by `0.5^(age / half-life)`
  (recent weeks matter most, no window cliff). Penalty: chi-square,
  `Σ (count − expected)² / expected`, scaled so one portion off target is
  about one point, and linear beyond 2 portions off so a neglected recipe
  gets a steady pull, not a burst. A recipe counts only from its `added`
  date (a new optional recipe field, filled from git once), so a new
  recipe starts on target instead of with a huge deficit.
- **Freshness.** Pulls portions toward their cooking day; spacing pushes
  them apart. For a dish that spoils fast, freshness wins and eating it on
  consecutive days comes out by itself. Waits for the fridge-life review
  (#195) and made-fresh recipes (#145): today many 1-day values belong to
  dishes made at mealtime, not stored.
- **Spread.** Penalise each meal's deviation from the day's mean
  (`Σ (x_m − total/n)²`), not plain squares, so the daily total is not
  pushed down. Snacks are left out. Evidence: protein spread over meals
  helps muscle protein synthesis (modest); carbs spread for blood sugar.

## Solver notes

- CP-SAT, deterministic seed. Only `planner/solver.py` imports OR-Tools.
- Quadratic terms: `t ≥ x²` by secant cuts at breakpoints that are dense
  near the target and geometric away from it (relative overestimate at
  most `(rho − 1)² / (4 rho)`), within a cut budget (40 is enough).
- Kcal are counted in steps of 10: matching kcal sums is a subset-sum
  search, and smaller numbers make it fast (seconds became under one).
- Stop on an **absolute** gap (about 1000 kcal², one day 32 kcal off), not
  a relative one: fixed history makes most of the penalty, so a percentage
  misleads.
- Results are plain data (sessions, batches, where each portion goes, the
  points per term); writing them to the diary is a separate step.

## Order of work

1. **First version:** templates, the planned flag, Plan / Accept / Clear
   plans, leftovers and next-day repeats, written over 7 days. Retire the
   old `plan_week` and its report (#103, L5).
2. Kcal terms, then session repeats.
3. A points breakdown in the UI and a config file in the diary folder, so
   weights can be tuned without a deploy.
4. Long-run frequency (with the `added` field), then freshness and spread
   as real plans show the need.

## Open questions

1. Frequency shares: equal per role to start; which recipes get more or
   less?
2. Made-fresh recipes (#145): until the recipe property exists, a list in
   the config.
3. Meal composition (`docs/spikes/meal-composition.md`): the templates here
   are option C of the spike in practice.
4. Should accepted or manual meals ever be moved by the planner (soft pins)?
   Today: never.
