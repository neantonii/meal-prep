# Planner

Status: built. The first version (#200) had hard templates; the model below
replaces it: existing meals are pins, the objective is a sum of named
terms, and each slot chooses an archetype ("Existing items are pins",
"Terms", "Archetypes"). "As built" lists where the code differs from the
design for now. The terms were
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

### Terms: the extension point

The objective is a sum of named **terms**. A term reads the shared
variables and adds its own: `build(ctx) -> points expression`, plus a name
for the points breakdown. The model builds the shared variables once
(`x`, `b`, the archetype choice per slot) and each term contributes;
adding a term is one class and changes nothing else. Pins never reach a
term: they only fix variables.

Two shapes cover the terms so far (see "Point system"): an **amount**
(`weight × ((x − target) / tolerance)²`, with the quadratic helper) and an
**event** (`weight × count`).

### Archetypes

What a meal looks like is decided per slot by an **archetype**: an explicit
choice variable `archetype[slot, a]`, exactly one per slot, among the
archetypes its mealtime allows. The solver picks the archetype and the
dishes; the slot pays for how badly its dishes fit the chosen archetype.
Nothing is enforced, so pinned contents never conflict: at worst the slot
pays a misfit. Rice every day is a possible plan; it just costs a lot.

Because the choice is a variable, later terms can act on it: per-day
preferences (one-dish on Sundays), frequency ("one-dish at most twice a
week"), diversity of archetypes over the week.

**Class shape** (kept shallow; subclass only for new behaviour, never for
new data):

```
Term (protocol)              build(ctx) -> points, name
└── Archetype (protocol)     fit(ctx, slot) -> points if chosen
    └── RoleArchetype        roles with target counts and penalties
        ├── Split            3 roles, one dish each (protein, carb, veg)
        ├── Single           1 role: one unit from a pool
        │   └── Bundle       Single whose pool is one fixed set
        └── (later) flexible kinds, e.g. 2-3 roles, optional extras
```

- **`RoleArchetype`** does the work. A role has a **pool** (recipes or
  bundles), a **target count range** (exactly 1; 0-2 for extras) and
  **missing / extra weights**. Fit = weighted shortfall and excess per role,
  plus a cost for anything in the slot no role takes. Linear: the
  shortfall and excess are counted only when the archetype is chosen.
- **Strict vs flexible is a weight, not a class.** A breakfast bundle has
  high missing and extra weights; a plate moderate ones, so the solver can
  leave the pattern when it really pays. "Hard" is a very large weight; no
  archetype is a hard constraint.
- **Pool units can be bundles**: a set of recipes eaten together is one
  unit (a breakfast set, apple + cottage cheese). Half a bundle pays its
  missing items. Bundles are authored data (the unused `Meal` bundles,
  `meals/*.yaml`, revived for this; `docs/spikes/meal-composition.md`).
- **Extensions add named terms on top of the fit**, e.g. a Split with
  pairing rules (requirement P1, rice-stick noodles only with minced meat:
  a penalty on that protein-carb pair), or a balanced-plate nutrient term.
- **Preferences on units** use the same machinery: oats on Mon / Wed / Fri
  (B1) is a per-weekday cost on one pool unit.
- **Archetype base cost**: plates slightly preferred over one-dish, etc.

**Configuration** (data, not code): which archetypes each mealtime allows,
with their pools and weights. Pools that differ by mealtime (cooked veg at
lunch, salad at dinner) are configuration, not subclasses.

```yaml
archetypes:
  lunch:
    - split:  {protein: modular_protein, carb: modular_carb, veg: modular_cooked_veg}
    - single: {pool: one_dish, base_cost: 0.5}
  dinner:
    - split:  {protein: modular_protein, carb: modular_carb, veg: fresh_salad_veg}
    - single: {pool: one_dish, base_cost: 0.5}
  breakfast:
    - single: {pool: [oats-set, eggs-set, sausage-set], strict: true}
  snacks:
    - bundle: apple-cottage
```

Takeout needs an archetype too, or the planner would "complete" a takeout
dinner with a plate around it: **eat out**, a Single whose pool is any
takeout entry, allowed at lunch and dinner. The planner never picks it for
an empty slot (takeout can't be planned); it matches pinned takeout at no
cost.

Starting weights (points; a leftover portion and a next-day repeat are 1):

| Archetype role | missing | extra |
|---|---|---|
| Split: protein, carb | 5 | 3 |
| Split: veg | 3 | 1 |
| Single: one-dish | 5 | 3 |
| Bundle item (breakfast, strict) | 5 | 5 |
| Snack bundle item | 1 | 0.5 |
| Anything no role takes | – | 1 |

### Where the first version's rules go

| First version | In this model |
|---|---|
| Hard template per empty slot (exactly one option, its roles) | `archetype[slot, a]` + `RoleArchetype` fit (soft) |
| Breakfast presets | Single over breakfast bundles, strict weights |
| Lunch / dinner "plate" and "one dish" options | Split and Single archetypes, per-mealtime pools |
| Snacks: fixed pair + any other snack | Bundle apple + cottage cheese; extras later |
| Slots holding anything skipped | gone: their meals are pins, the slot is completed or pays a misfit |
| `eaten` set (once-a-day, repeats) | gone: pinned `x`, the terms read all `x` alike |
| Once a day (hard) | event term, 5 points per extra use in a day |
| Next-day repeat (1 point, special-cased for fixed days) | event term over all `x`, history days included |
| Leftovers (1 point per portion, planned batches only) | event term over every batch, manual ones included |
| `uses ≤ batches × servings` | hard, unchanged (diary invariant), with binned and unassigned portions counted |
| Meal on or after its session's date | hard, unchanged (diary invariant) |
| Truncated last session (leftovers not charged) | a parameter of the leftover term |
| Session of a meal = its cycle day | session is a variable index; candidates: cycle session + sessions with stock |
| Points per term in the plan | one name per term, the breakdown is automatic |
| Deterministic solve, time limit | unchanged |

### As built

- **No bundles yet.** Every breakfast and the snack pair are Splits whose
  roles name recipes ("oats breakfast" = any overnight oats + boiled eggs
  + flat white; "hot breakfast" = fried eggs, the sausage skillet or egg
  muffins + latte; snacks: apple + cottage cheese bowl, or the clementine
  bowl). Bundles (a set eaten whole as one pool unit) come when a meal
  needs them. Archetypes are code (`planner/archetypes.py`), not yet a
  config file.
- **Unassigned portions are stock.** A planned dish may come from its
  slot's cycle session (cooked there) or from an earlier batch with
  unassigned portions that is still good: within its fridge life, or
  freezer-friendly. The write-back moves those portions onto days,
  flagged `planned`. New batches are only cooked in planned sessions.
- **Planned batches are counted on the recipe line** (`planned_batches`
  on a session item: how many of its `batches` the plan added and nobody
  has accepted). Meals carry only `planned`. Clear plans takes off the
  planned batches of open sessions (keeping what manual meals need),
  sends every planned meal from today on back to Unassigned, and leaves
  past days alone. A cooked session keeps its batches (a fact). Accept
  clears both flags; removing a batch takes a planned one first.
- **Additions never overfill a role**: what the plan adds under the chosen
  archetype fits in the room the pins leave (a hard limit on additions
  only, never on pins), and it only adds dishes the chosen archetype
  takes. Shortfall is linear (`short ≥ target × chosen − count`), pinned
  excess and pinned unknown dishes are a constant × the choice. This keeps
  the bound tight: a 7-day plan is proven optimal in 1-3 s (a big-M
  version timed out at 10 s with poor plans).
- **A session the horizon cuts off** pays 1% of the leftover points, so
  its batches stay just enough (with no charge at all the solver cooked
  arbitrary batches into Unassigned).
- **History**: the day before the horizon and the start day's meals from
  the previous cycle are fully pinned slots.
- OR-Tools note: a variable's `proto.domain[-1]` does not index from the
  end; bounds are read through a helper.

### Scoring and Explain

The same model scores any week ahead, the planner's meals and yours alike:
every dish is pinned, no batch changes, each meal is read as its closest
archetype, and the hard rules are checked and reported instead of
enforced (so an inconsistent file still gets a bill). Every term labels
its points with a place (a meal, a day or a session) and a reason, so
the result is a bill: total, points per term, and lines such as "Sat
dinner · plate: 1 extra protein · 3". An empty meal is not planned yet and
costs nothing when scoring. `GET /api/plan/explain` serves it; the week
page's **Explain** toggle shows the bill and tags each meal with its
archetype and points. Next: "why not something else?" per meal (free one
slot, re-solve, compare) and what-if with a pinned alternative.

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
| Archetype fit | event | per role (Archetypes) | next (hard templates in the first version) |
| Same recipe twice in a day | event | 5 points | next (hard in the first version) |
| Archetype preferences | event | per day / frequency | later |
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
2. **Pins, terms and archetypes:** the model above. Half-filled meals get
   completed, existing batches and unassigned stock count, history is
   pinned slots, archetypes are chosen per slot and scored.
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
6. Meal composition (`docs/spikes/meal-composition.md`): archetypes with
   bundle pools answer it (option C); the spike can be closed with this
   design.
7. Should accepted or manual meals ever be moved by the planner (soft
   pins)? Today: never.
