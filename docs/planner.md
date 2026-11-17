# Planner

Status: first version built (#200: hard templates, Plan / Accept / Clear
plans). Next: the model below, where existing meals are pins and templates
are soft (see "Existing items are pins", "Soft templates"). The terms were
first tried in a sandbox (branch `sandbox/session-optimizer`, reference
only). The meal
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
  leftover portions unassigned. What is already there (manual meals,
  takeout, accepted meals) stays and is planned around: a half-filled meal
  gets completed (see "Existing items are pins"). The first version left
  any slot that held something alone, so a lunch with only a carb stayed
  that way.
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

### Existing items are pins

One model, built the same way whatever already exists. Existing items never
change how a constraint or term is written: they only fix variables.

- **Variables.** `x[slot, recipe, session]`: this recipe, a portion of this
  session's batch, is in this slot. `b[session, recipe]`: batches cooked.
  Slots cover the horizon and the history days the terms reach back to.
  Candidate sessions for a slot: its cycle session and any session with
  stock of the recipe (unassigned portions, older batches), so a frozen or
  older portion is representable.
- **Pins.** A meal on a day fixes its `x = 1`. A cooked session fixes
  `b = its batches`; a planned session keeps at least its manual batches
  (`b ≥`, open question). History days are fully pinned.
- **Hard constraints are only what the diary already guarantees**, so pins
  can never make the model infeasible: a portion is eaten on or after its
  session's date; meals from a batch (plus binned portions) never exceed
  `b × servings`; cooked batches are fixed. Unassigned portions are
  capacity not yet placed.
- **Everything else is soft**, including the templates and "once a day".
  Rejected: hard templates with constraints dropped locally where pins
  break them (fragile, and every new rule would need its own exceptions).
- **Write-back is the difference:** new meals are the `x = 1` that were not
  pinned; new batches are `b` minus what existed.
- **History** enters at two scales. Short reach (next-day repeats, rolling
  kcal): the last few logged days are slots with every `x` pinned, the
  terms run over them unchanged, and presolve turns them into constants.
  Long reach (frequency over weeks): precomputed per-recipe counts, not
  slot variables, so a month of history does not grow the model.

### Soft templates

Templates stay as the local recommendation ("I like a meal of protein +
carb + veg"), but they are scored, not enforced: rice every day is a
possible plan, it just costs a lot.

- **Roles** are groups of recipes: protein, carb, cooked veg, salad,
  one-dish, each breakfast-set item, apple, cottage cheese, takeout, and
  "unknown" (fits no role). `count[slot, role] = Σ x` over the role's
  recipes, pinned or planned alike.
- **An option** is a recommended composition: a target count per role.
  Lunch "plate" = protein 1, carb 1, cooked veg 1, the rest 0; lunch "one
  dish" = one-dish 1; "eat out" = takeout 1; a breakfast set = 1 of each of
  its recipes.
- **A slot pays for its closest option:**
  `min over options of Σ_role (missing × w_missing[role] + extra × w_extra[role])`,
  linear with one choice flag per option (exactly one per slot), the
  shortfall and excess counted only for the chosen one. An option may
  carry a base cost (plates preferred over one-dish; oats on Mon / Wed /
  Fri as a per-weekday cost).
- **Consequences.** A half-filled meal is completed because completing it
  is cheaper. A takeout dinner picks "eat out" at no cost. Two proteins
  placed by hand pay their "extra" and nothing breaks. An empty slot pays
  the missing points of its closest option, so the planner fills it; low
  weights make snacks optional.

Starting weights (points; a leftover portion and a next-day repeat are 1):

| Role | missing | extra |
|---|---|---|
| protein, carb (main meals) | 5 | 3 |
| veg, salad | 3 | 1 |
| one-dish | 5 | 3 |
| breakfast set item | 2 | 2 |
| apple, cottage cheese | 1 | 0.5 |
| other snack | – | 0.2 |
| unknown item | – | 1 |
| same recipe twice in a day | – | 5 |

### First version (built, being replaced)

Hard templates per empty slot (exactly one option; roles, presets,
alternatives, extras). Slots holding anything were skipped, existing
batches and unassigned stock were not in the model, and "fixed vs planned"
was special-cased in each term.

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
| Templates | event | soft, per role (table above) | next (hard in the first version) |
| Same recipe twice in a day | event | 5 points | next (hard in the first version) |
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

1. **First version** (done, #200): hard templates, the planned flag,
   Plan / Accept / Clear plans, leftovers and next-day repeats over 7 days;
   the old `plan_week` and its report retired.
2. **Pins and soft templates:** the model above. Half-filled meals get
   completed, existing batches and unassigned stock count, history is
   pinned slots.
3. Kcal terms, then session repeats.
4. A points breakdown in the UI and a config file in the diary folder, so
   weights can be tuned without a deploy.
5. Long-run frequency (with the `added` field), then freshness and spread
   as real plans show the need.

## Open questions

1. Unassigned stock: may the planner put existing unassigned portions on
   days (as planned meals)? Proposed: yes; that is what the slot is for
   (`docs/freezer.md`).
2. Planned sessions with manual batches: `b ≥ yours` (the plan may add
   batches of a recipe you batched) or `b = yours`? Proposed: `≥`.
3. How far back history reaches per term (a day for repeats, the window
   for rolling kcal, weeks for frequency).
4. Frequency shares: equal per role to start; which recipes get more or
   less?
5. Made-fresh recipes (#145): until the recipe property exists, a list in
   the config.
6. Meal composition (`docs/spikes/meal-composition.md`): soft templates are
   option C of the spike in practice.
7. Should accepted or manual meals ever be moved by the planner (soft
   pins)? Today: never.
