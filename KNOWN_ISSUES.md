# KNOWN_ISSUES.md — Architecture & Correctness Findings

Audit of the Meal Prep codebase conducted on the full repository at commit `d4f8440`.
All findings below were verified by executing code against the real data, not by reading alone.

**Scope audited:** `src/meal_prep/`, `tests/`, `schemas/`, `data/`, `recipes/`, and the top-level docs.

---

## How to use this document

* Work items are ordered by **severity**, not effort.
* Each item has an ID (`KI-NN`), evidence with file/line references, impact, a proposed fix, and a status.
* We resolve items **one at a time**: pick item → discuss approach → approve → implement → verify → mark `Resolved`.
* Status values: `Open` · `In discussion` · `Approved` · `In progress` · `Resolved` · `Won't fix` · `Deferred`

### Severity legend

| Level | Meaning |
| :--- | :--- |
| **Critical** | Silently produces incorrect nutrition/cost output, or a documented command does not exist |
| **High** | Silent wrong-machine behavior, duplicated source of truth, or environment fragility that will bite |
| **Medium** | Correctness edge cases, ambiguous data semantics, missing guardrails |
| **Low** | Hygiene, dead code, documentation drift |

---

## Summary

| ID | Severity | Title | Status |
| :--- | :--- | :--- | :--- |
| KI-01 | Critical | Duplicated calculation engines (`Recipe.compute_*` vs `calculator`) | Open |
| KI-02 | Critical | `package.container == package.unit` silently corrupts conversions | Resolved |
| KI-03 | High | Conversion-graph cache ignores the units registry that built it | Open |
| KI-04 | High | CWD-coupled path resolution + fail-open validation | Open |
| KI-05 | High | Ingredient `aisle` never validated against `aisles.yaml` | Open |
| KI-06 | High | `README` documents a `meal_prep.cli` module that does not exist | Open |
| KI-07 | Medium | Ad-hoc ingredient shelf-life capping overrides declared storage | Open |
| KI-08 | Medium | Cost model is prorated marginal cost, not purchase outlay | Open |
| KI-09 | Medium | Per-serving macros derived from already-rounded batch values | Open |
| KI-10 | Medium | `RecipeYield.servings: float` vs `PreparedRecipe.servings: int` | Open |
| KI-11 | Medium | `bunch` is simultaneously a count unit and a packaging container | Open |
| KI-12 | Medium | `fresh-lemon` declares two aliases of the same count unit | Resolved |
| KI-13 | Medium | "Cooking loss" sign is misleading for water-absorbing grain recipes | Open |
| KI-14 | Medium | Renderer re-declares Cooklang regexes instead of importing them | Resolved |
| KI-15 | Medium | No schema-generation pipeline; JSON schemas drift from models | Open |
| KI-16 | Low | Dead variables in `renderer.py`; loss/batch totals never rendered | Open |
| KI-17 | Low | No `pyproject.toml` / dependency manifest | Open |
| KI-18 | Low | Documentation drift on file/aisle/category counts | Open |
| KI-19 | Low | Unused public API surface | Open |
| KI-20 | High | Business logic and I/O live on Pydantic models (violates model-purity rule) | In progress |

---

## KI-01 — Duplicated calculation engines

**Severity:** Critical
**Status:** Open

### Symptom
`Recipe` and `calculator` each contain a complete, independent implementation of the same
nutrition/cost/weight math. They agree today by coincidence of discipline, not by construction.

### Evidence
* `src/meal_prep/models/recipe.py:84-190` — `compute_raw_batch_weight_g`, `compute_cooking_loss_percent`, `compute_macros`, `compute_cost`, `compute_safe_fridge_days`, plus the `portion_cooked_weight_g` property at `:79-82`.
* `src/meal_prep/calculator.py:116-238` — `prepare_recipe` recomputes all of the same values.
* The `Recipe` methods are referenced **only from tests**: `tests/test_recipes.py:283,288,296,301,311,423,426,430`. Production goes through `calculator`.

### Verified
Both paths currently produce identical output for `air-fried-chicken-breast`:
```
calculator batch kcal: 1186.6 | recipe.compute_macros kcal: 1186.6
calculator batch cost: 23.07  | recipe.compute_cost: 23.07
calculator serving kcal: 296.6 | recipe sm: 296.6
```

### Impact
Two sources of truth for every derived number. The copy exercised **only by tests** is the one
most likely to rot, and a future change to (e.g.) rounding, cost proration, or loss handling
applied to one path will silently diverge. Tests then validate the *unused* implementation
while production emits different numbers.

### Proposed fix
Make `calculator` the single source of truth. Either:
1. **Delegate** — rewrite the `Recipe.compute_*` methods to call `prepare_recipe(...)` and return the relevant fields, or
2. **Delete** — remove them and update `tests/test_recipes.py` to assert against `PreparedRecipe`.

Recommendation: **delete** and re-point tests, since `PreparedRecipe` already exposes every field.
The `Recipe.portion_cooked_weight_g` property is a simple `cooked_g / servings` derivation and can stay.

---

## KI-02 — `package.container == package.unit` silently corrupts conversions

**Severity:** Critical
**Status:** Resolved — implemented; 66 tests pass

### Symptom
`PackageInfo` permits `container` and `unit` to be the same string. In the conversion graph,
the packaging edge is added **after** ingredient conversions and `add_edge` is last-write-wins,
so the packaging weight silently overwrites a real, correct conversion.

### Evidence
* `src/meal_prep/models/ingredient.py:12-24` — `PackageInfo` has no cross-field constraint.
* `src/meal_prep/models/conversion_graph.py:117-118` — `add_edge` overwrites both directions unconditionally.
* `src/meal_prep/models/conversion_graph.py:154` — `add_edge(container, "g", pkg.container_weight_g)` runs *after* step 3 (ingredient conversions at `:134-144`).

### Verified
Constructed an eggs-like ingredient with `container: piece, unit: piece, amount: 12, container_weight_g: 600`
plus a legitimate `piece -> g` factor of `50`:
```
container==unit: piece->g = 600.0 (expected 50.0 from conversions)
```
A 12× error in every macro and cost, with no error raised.

### Impact
Silent, plausible-but-wrong nutrition output. This is the worst class of bug for this system:
nothing crashes and the numbers look reasonable.

### Implemented fix — validate-then-augment graph construction
Validate the **directed** edge set before adding the automatic reverse edges. This is what makes the
cycle check meaningful: every healthy ingredient legitimately has a reciprocal edge, so a cycle test
run after augmentation would flag everything.

```
1. Build directed edges, in this order:
     a. implicit  container -> unit  = amount          (never omit)
     b. authored  conversions
     c. universal defaults (mass -> g, volume -> ml)
   NOTE: no container_weight_g edge is ever emitted.
2. Validate the directed set:
     - no self-reference            (catches container == unit)
     - no conflicting pair          (same pair, different factor; identical factor = idempotent no-op)
     - no directed cycle
3. Augment with reverse edges, then build the conversion map.
4. Derive container_weight_g (see below), then post-validate:
     - container must reach grams
     - every recipe-referenced unit must reach grams
5. Taxonomy validation:
     - container in units.yaml packaging_containers
     - unit in the units taxonomy OR an endpoint of an authored conversion
       (custom units such as `scoop` stay legal when explicitly bridged)
```

Cycle detection has independent value: `bag -> g` (implicit) plus authored `g -> cup`, `cup -> bag`
produces a directed cycle today and PARSES cleanly. It also catches the 3-node case that the
dimension-pair and duplicate-edge checks cannot see.

**Re-adding an edge is an error (not a no-op).** Repeating a pair — in either direction — is rejected
rather than silently ignored. A conversion map holds one factor per pair, so a second definition would
vanish without trace; an add that changes nothing is a mistake, so it is reported. This rejects the
pattern found in four ingredients (`extra-lean-ground-turkey` `pack -> g = 450`, `extra-lean-ground-beef`
`pack -> g = 454`, `rice-stick-noodles` `bag -> g = 454`, `wild-pollock-fillet` `bag -> g = 400`): in each,
`package.unit` is already `g`, so the authored conversion merely restates the implicit edge. Those four
were rewritten to `conversions: []`.

**Float handling.** Factors are IEEE-754 binary64; all 36 distinct values in the catalog are exactly
representable (integers and dyadics), and two identical YAML literals parse bit-identically, so exact
comparison is reliable. Note `(1/f)*f == 1.0` fails for `f = 0.915` (`0.9999999999999999`), which is why
reciprocals are *derived* rather than compared.

**Follow-up refactor (architecture).** The graph was extracted into a standalone, dependency-free model:
`conversion_graph.py` now imports only stdlib and exposes `ConversionEdge` (frozen, self-validating),
`ConversionGraph` (immutable — `MappingProxyType` + `frozenset`), and `build_graph(edges)`. Domain glue
(package/container validation, alias normalization, universal mass/volume edges) lives in
`_build_ingredient_graph` in `ingredient.py`. `Ingredient.get_conversion_factor` was deleted; rounding was
removed from `ConversionGraph.convert` (presentation rounds). `container_weight_g` moved to `Ingredient`,
derived via `graph.factor(container, "g")`.

### Related: `container_weight_g` becomes derived (single source of truth)
Drop the authored field and compute it on the ingredient during load, **after** validation passes and
the graph exists. The value is then a pure function of the authored conversions — no circularity, since
the field is never read during graph construction. Zero self-references exist in the data, and only four
conversions name the container noun (all identical-factor no-ops).

Transition requirement: when the authored field is removed from YAML, the old and derived values must be
compared during the change so the discrepancy is *reported*, not silently repriced. Blast radius of the
derivation itself is a single 1-cent change (`dijon-mustard` `$0.94 -> $0.93`, rounding). KI-12's lemon is
the one real discrepancy and is resolved there.

### `conversions` is now optional
The `min_length=1` floor was removed from both `Ingredient.conversions` and the JSON schema, so a package
whose `unit` is already a mass unit needs no authored conversion. This is what lets a 500 g box of raisins
be written honestly instead of inventing a bridge to satisfy the validator — which is how the four
redundant container-named conversions above came to exist.

### Out of scope (deferred, tracked separately)
* Hoisting recipe-unit resolution out of `load_recipe_file` into a shared helper (`recipe.py:370-375`
  already implements this check).

---

## KI-03 — Conversion-graph cache ignores the units registry that built it

**Severity:** High
**Status:** Open

### Symptom
The cached `ConversionGraph` is keyed on nothing. A graph built from one `UnitsRegistry` is returned
for a later call passing a *different* registry.

### Evidence
* `src/meal_prep/models/ingredient.py:170` — `_conversion_graph: Any = PrivateAttr(default=None)`
* `src/meal_prep/models/ingredient.py:200-205` — `get_conversion_graph` returns the cached object if non-`None`, ignoring the `units` argument entirely.

### Verified
```
cache returns same object for different registry: True
```
(`oil.get_conversion_graph(units_A) is oil.get_conversion_graph(units_B)`)

### Impact
Any second registry — a test fixture, a seasonal/variant `units.yaml`, a future unit-system toggle —
silently receives factors computed from whichever registry loaded first. Order-dependent,
non-obvious, and it fails silently.

### Proposed fix
Key the cache by registry identity, e.g. `dict[int, ConversionGraph]` keyed on `id(units)`, or store
`(weakref(units), graph)`. Alternatively make the registry a required constructor argument of
`Ingredient` and build the graph once at load time (which `load_all_ingredients` already does via
`units=units`). The explicit-construction route is cleaner and removes the lazy path entirely.

---

## KI-04 — CWD-coupled path resolution + fail-open validation

**Severity:** High
**Status:** Open

### Symptom
Every loader defaults to a **relative** path, so the package only works when the process is started
from the repository root. Additionally, `Ingredient`'s validator reaches into the ambient filesystem
for a default units registry and **swallows any failure**, disabling validation.

### Evidence
* `src/meal_prep/library.py:29-30` — `data_dir: Path | str = Path("data")`, `recipes_dir: Path | str = Path("recipes")`
* `src/meal_prep/renderer.py:242` (in `render_all_recipe_cards`) — re-hardcodes `load_aisles(Path("data/aisles.yaml"))`
* `src/meal_prep/models/units.py:139-143` — `get_default_units` falls back four directories up: `Path(__file__).resolve().parent.parent.parent.parent / "data" / "units.yaml"`
* `src/meal_prep/models/ingredient.py:102-106` — `try: units_reg = get_default_units() ... except Exception: return self`

### Impact
* Tools, scripts, and tests behave differently depending on the invoking directory.
* The fail-open branch means conversion-uniqueness validation can silently **not run**. Which
  validation applies depends on the filesystem at import time. This also makes KI-02/KI-05-style
  data errors more likely to slip through.

### Proposed fix
1. Anchor resolution to the package/repo root: define one `PROJECT_ROOT` (or accept explicit
   `data_dir`/`recipes_dir` on every public entry point, which `MealPrepLibrary.load` already does).
2. Remove the `parent.parent.parent.parent` fallback in `get_default_units`.
3. Replace the fail-open `except Exception: return self` with an explicit failure — if the units
   registry genuinely cannot be located, raise rather than skip validation. If a "no units required"
   mode is needed, express it as an explicit optional argument instead of an exception swallow.
4. Remove the hardcoded `data/aisles.yaml` from `render_all_recipe_cards`.

---

## KI-05 — Ingredient `aisle` is never validated against `aisles.yaml`

**Severity:** High
**Status:** Open

### Symptom
`ingredient.aisle` is checked against the **filename stem** but never against the canonical aisle
taxonomy. An ingredient can therefore declare an aisle that does not exist.

### Evidence
* `src/meal_prep/models/ingredient.py:224-233` — `load_ingredients_file` compares `ingredient.aisle` to `file_path.stem` only. There is no `aisles` parameter.
* `src/meal_prep/library.py:46-47` — `load_aisles` result is stored but never passed into `load_all_ingredients`.
* `AislesConfig.valid_ids` (`src/meal_prep/models/aisle.py:43-45`) has **0 references** anywhere in `src/` or `tests/`.

### Impact
Renaming or removing an aisle in `aisles.yaml` will not surface the now-dangling ingredients. The
taxonomy is documented (`README`, `AGENTS.md`) as a single source of truth, but nothing enforces it.
`valid_ids` exists precisely for this and is unused.

### Proposed fix
Thread the `AislesConfig` into `load_all_ingredients` / `load_ingredients_file` and assert
`ingredient.aisle in aisles.valid_ids`, raising a clear error naming both the offending ingredient
and the invalid aisle. `MealPrepLibrary.load` already loads aisles before the catalog, so no call-site
restructuring is needed.

---

## KI-06 — `README` documents a `meal_prep.cli` module that does not exist

**Severity:** High
**Status:** Open

### Symptom
The README's Developer Quickstart advertises a CLI entry point. It is not implemented.

### Evidence
* `README.md` (Developer Quickstart): `PYTHONPATH=src python3 -m meal_prep.cli audit <category> <recipe-slug>`
* `ls src/meal_prep/` → `__init__.py  calculator.py  library.py  models  renderer.py` — no `cli.py`.
* `PYTHONPATH=src python3 -c "import meal_prep.cli"` → `ModuleNotFoundError: No module named 'meal_prep.cli'`

### Impact
A documented, user-facing command fails immediately. Erodes trust in the rest of the doc, and the
README is the stated entry point for new developers.

### Proposed fix
Either implement `src/meal_prep/cli.py` with an `audit` subcommand (thin wrapper over
`MealPrepLibrary.review_math`, using `argparse`), or remove the command from the README.
Recommendation: **implement it** — `review_math` already exists and this is ~30 lines, and the
`AGENTS.md` verification workflow references an equivalent one-liner.

---

## KI-07 — Ad-hoc ingredient shelf-life capping overrides declared storage

**Severity:** Medium
**Status:** Open

### Symptom
The effective fridge life is silently `min(recipe_declared_days, ingredient_shelf_life_days)`,
conflating **raw ingredient** shelf life with **cooked dish** shelf life.

### Evidence
* `src/meal_prep/calculator.py:149` — `min_safe_days = recipe.storage_info.fridge_days`
* `src/meal_prep/calculator.py:162` — `min_safe_days = min(min_safe_days, ing.shelf_life_days)`

### Verified
Two recipes are silently cut from their declared value:
```
air-fried-chicken-breast:           recipe declares 4d, effective 3d (silent cap)
pan-seared-roasted-pork-tenderloin: recipe declares 4d, effective 3d (silent cap)
```
(`boneless-chicken-breast` has `shelf_life_days: 3`, i.e. its *raw* refrigerated life.)

### Impact
The author's explicitly declared cooked-dish storage window is overridden by an unrelated raw-ingredient
freshness number, with no warning. Cooked chicken does not inherit raw chicken's 3-day limit.

### Proposed fix
Separate the concepts explicitly. Options:
1. Treat the two as independent constraints and **warn/error** when the recipe declares more than an
   ingredient permits, rather than silently capping.
2. Model cooked-dish shelf life on the recipe only, and use ingredient shelf life solely for
   *purchasing/freshness* guidance.
Recommendation: **(1)** now (non-silent), with a note that **(2)** is the more correct long-term model.

---

## KI-08 — Cost model is prorated marginal cost, not purchase outlay

**Severity:** Medium
**Status:** Open

### Symptom
`batch_cost` bills only the grams actually used, derived from `price / container_weight_g`. For
pantry items bought in bulk, this is far below what the user must actually spend.

### Evidence
* `src/meal_prep/models/ingredient.py:172-175` — `price_per_100g = (reference.price / package.container_weight_g) * 100`
* `src/meal_prep/calculator.py:157-158` — `factor = grams / 100.0; item_cost = factor * ing.price_per_100g`

### Impact
A $4 spice bottle contributing 1 tsp reports roughly $0.08. The README roadmap promises
"**Cost per serving** and batch preparation cost" for budgeting and a consolidated grocery list —
budgeting needs the *outlay* (do I need to buy this bottle at all?), which this cannot express.

### Proposed fix
Expose both numbers distinctly rather than replacing one with the other:
* `batch_cost` — marginal/prorated cost of ingredients consumed (keep as-is, it is useful).
* `batch_purchase_cost` (or `shopping_cost`) — sum of full package prices for the distinct packages a
  batch requires (ceil of `grams / container_weight_g` per ingredient).

This also lays the groundwork for the planned consolidated shopping list.

---

## KI-09 — Per-serving macros derived from already-rounded batch values

**Severity:** Medium
**Status:** Open

### Symptom
Batch macros are rounded to 1 decimal, then serving macros are computed by dividing the **rounded**
batch values. This is double rounding.

### Evidence
* `src/meal_prep/calculator.py:201-204` — `batch_macros_dict[key] = round(batch_macros_dict[key], 1)`
* `src/meal_prep/calculator.py:207-211` — `serving_macros_dict = {key: round(batch_macros_dict[key] / servings, 1) ...}` — reads the rounded dict.
* Same pattern in `src/meal_prep/models/recipe.py:145-157`.

### Impact
Small per-field error (up to ~0.1 × servings across the batch), and per-serving values may not sum
back to the batch totals. Minor numerically, but this is a "deterministic math" system per
`AGENTS.md`, where the guarantee is supposed to hold exactly.

### Proposed fix
Compute per-serving values from the **unrounded** accumulator, then round each independently:
keep the raw float sums, round once for `batch_macros`, and round `raw / servings` for `serving_macros`.
Same change in both places (moot once KI-01 collapses them to one).

---

## KI-10 — `RecipeYield.servings: float` vs `PreparedRecipe.servings: int`

**Severity:** Medium
**Status:** Open

### Symptom
The declared type and the computed type disagree, and fractional servings are accepted by the parser.

### Evidence
* `src/meal_prep/models/recipe.py:20` — `servings: float = Field(..., gt=0, ...)`
* `src/meal_prep/calculator.py:46` — `servings: int` on `PreparedRecipe` (populated at `:191` from the float).
* Verified: `RecipeYield(servings=2.5, cooked_g=500)` → accepted, `2.5` (`float`).

### Impact
A typo such as `servings: 4.5` passes parsing and silently produces 4.5 portions — and inconsistent
per-serving percentages elsewhere. The `PreparedRecipe` annotation is also not enforced by the
dataclass, so the declared `int` is misleading.

### Proposed fix
Make `servings` an `int` with `gt=0` on `RecipeYield` (portions are discrete), and keep `int` on
`PreparedRecipe`. If fractional yields are genuinely needed, make both `float` and state the decision.
Recommendation: **`int`** — all 12 existing recipes use whole numbers.

---

## KI-11 — `bunch` is simultaneously a count unit and a packaging container

**Severity:** Medium
**Status:** Open

### Symptom
The same token appears in two distinct namespaces, so resolution depends on which lookup path runs.

### Evidence
* `data/units.yaml` — `bunch` is listed under `count.allowed` (`bunch: [bunch, bunches]`) **and** under `packaging_containers`.
* Verified: `is_valid_unit("bunch") == True` **and** `is_valid_container("bunch") == True`.
* `src/meal_prep/models/conversion_graph.py:29-42` — `normalize` checks units first, then containers.

### Impact
Ambiguous intent: is `bunch` a measured count or a package? Today the units branch wins by ordering,
which is incidental rather than contractual. A `bunch`-packaged herb is likely to resolve unexpectedly.

### Proposed fix
Decide the semantics and encode it once. Either remove `bunch` from `packaging_containers` (keeping it
a count unit), or namespace containers distinctly. Then add a load-time assertion in `load_units`
that no token appears in both sets — cheap and prevents recurrence.

---

## KI-12 — `fresh-lemon` declares two aliases of the same count unit

**Severity:** Medium
**Status:** Resolved in design — data fix identified (110 g), container-noun decision outstanding

### Symptom
Two conversions describe the same physical concept with the same factor, while the `package` block
implies a different (and more realistic) piece weight. The dedup validator does not catch it.

### Evidence
* `data/ingredients/produce.yaml` (`fresh-lemon`) — `conversions` include both `item -> g = 50.0` and `piece -> g = 50.0`; `package` is `unit: item, amount: 1, container_weight_g: 110`.
* Verified across the catalog:
  ```
  DISCREPANCY fresh-lemon: unit 'item'->g=50.0 but package implies 110.000
  ```
* `src/meal_prep/models/ingredient.py:108-118` — `get_dim_key` returns `(dim, canonical)` for count units, so `item` and `piece` are treated as **different** dimensions and the cross-dimension/duplicate checks both miss this pair. (All other 27 ingredients are consistent — this is the sole outlier.)

### Impact
`@fresh-lemon{1%piece}` records 50 g while the package block says a lemon is 110 g. Macros and cost
for any lemon-bearing recipe are off by ~2.2×. The dual `item`/`piece` aliasing also bypasses the
guardrail that was specifically designed to prevent redundant conversions.

### Resolved by label data (retail label supplied)
The retail label for **"Lemon Large 1 Count"** ($1.49) declares nutrition **per 55 g**, and that basis
is exactly what `macros_per_100g` was derived from:

```
nutrient          label/55g   x100/55   data/100g   match
calories_kcal            15     27.27       27.3    yes
fat_g                   0.2      0.36        0.4    yes
carbs_g                   5      9.09        9.1    yes
fiber_g                   2      3.64        3.6    yes
sugars_g                  1      1.82        1.8    yes
protein_g                 1      1.82        1.8    yes
potassium_mg             75    136.36       136    yes
sodium_mg                 1      1.82         2    ~   (label rounds to 1 mg; 1.8 -> 2 is the same rounding)
```

Every nutrient reconciles; sodium differs only by label rounding at 1 mg precision.

So **55 g is a *serving* of the fruit, not a whole fruit.** Crunching the numbers:

| quantity | value | note |
| :--- | :--- | :--- |
| Package weight | **110 g** | whole large lemon + peel; matches USDA large fruit (108 g, 3-1/2" dia) |
| `item -> g` | **110.0** | one lemon = one whole fruit |
| Serving | 55 g | label basis, not a package size |
| Recipe `0.5 item` | 55 g | exactly one label serving -> **15.0 kcal** |
| Recipe cost | 0.5 x $1.49 = **$0.745** | arithmetically exact; today it under-reports as $0.34 |
| Juice yield | ~45-50 ml | the current `50` appears to be *juice yield*, not item mass |

**Decision: use 110 g.** `container_weight_g` stays 110 (so `$1.35/100g` is unchanged and derived ==
declared), `item -> g = 110`, and `0.5 item` lands on exactly one label serving. This makes the derived
weight agree with the declared weight, resolving the discrepancy without a special case, and fixes the
recipe cost under-reporting.

The dual `item`/`piece` aliasing is not itself redundant — they are distinct taxonomy entries that
genuinely coincide here — but the load-time consistency check below still earns its place.

### Proposed fix
1. **Data:** set `item -> g = 110.0` and `piece -> g = 110.0`; keep `container_weight_g: 110`.
2. **Container noun:** `pack` of one lemon is wrong — a pack implies multiples. A lone loose lemon
   is a *single-item* produce purchase, so the container noun should express that. No existing
   taxonomy value is a clean fit: `bunch` implies several herbs/greens bound together, `clamshell`
   implies a lidded retail punnet, and `loaf`/`carton`/`bottle` are clearly wrong. **Open question:**
   either (a) add a single-item container noun to `packaging_containers` (e.g. `count` or `each`),
   or (b) reuse `pack` and accept the semantic stretch, or (c) leave `container` as the loose-lemon
   noun that already exists. Needs a decision before the YAML is edited.
3. **Engine:** extend dedup so count-dimension aliases resolving to the same measurable concept are one
   dimension; plus the load-time check that `convert(1, package.unit, "g")` agrees with
   `container_weight_g / amount` within tolerance (subsumed by the KI-02 derive-and-compare step).

---

## KI-13 — "Cooking loss" sign is misleading for water-absorbing grain recipes

**Severity:** Medium
**Status:** Open

### Symptom
The field is named and formatted as a *loss*, but for boiled grains the cooked weight exceeds the raw
weight (water absorption), yielding large negative values.

### Evidence
* `src/meal_prep/calculator.py:193-195` — `cooking_loss_percent = (1.0 - cooked/raw) * 100`
* Verified across all 12 recipes:
  ```
  boiled-basmati-rice:   raw=  60.6 cooked= 185.0 loss=-205.3%
  boiled-rice-stick-noodles: raw=  63.0 cooked= 140.0 loss=-122.2%
  boiled-roasted-buckwheat:  raw=  73.0 cooked= 178.0 loss=-143.8%
  capellini-spezzati:    raw=  88.0 cooked= 160.0 loss= -81.8%
  ```
  versus genuine losses for proteins (chicken `32.3%`, pork `40.1%`, pollock `45.1%`).

### Impact
A `-205.3% loss` reading is nonsensical to a user and signals the metric conflates two phenomena
(moisture/fat loss vs. water uptake). It also mixes in untracked water, which the authoring skill
explicitly excludes from ingredient tokens.

### Proposed fix
Replace the single signed value with an explicit yield concept:
* Report `cooked_yield_percent = cooked_g / raw_g * 100` plus `weight_change_percent` (signed), or
* Classify recipes (e.g. `hydration` vs `loss`) and label accordingly.
Recommendation: expose a signed **weight change** plus an unsigned **cooked yield**, and reserve
"loss" language for the negative-only case.

---

## KI-14 — Renderer re-declares Cooklang regexes instead of importing them

**Severity:** Medium
**Status:** Resolved — Cooklang tokenization extracted to a pure engine, shared by parser and renderer

### Symptom
The three Cooklang parsing patterns are duplicated verbatim in the renderer rather than shared with
the parser.

### Evidence
* Canonical definitions: `src/meal_prep/models/recipe.py:194-202` (`_INGREDIENT_PATTERN`, `_COOKWARE_PATTERN`, `_TIMER_PATTERN`).
* Duplicated inline: `src/meal_prep/renderer.py:44-46`, `:56`, `:69` — confirmed as re-declarations.

### Impact
Parsing and rendering can disagree: a syntax change applied to one site makes the parser and the card
renderer recognize different tokens, producing drifting badges/labels or silently unformatted text.
The two definitions are identical today purely by maintenance discipline.

### Proposed fix
Export the compiled patterns from `models/recipe.py` and import them in `renderer.py`. The
substitution callbacks differ, so only the patterns need sharing.

### Implemented fix — `engines/cooklang.py`
The tokenizer and the three compiled patterns were moved into a pure, stdlib-only engine
(`engines/cooklang.py`) alongside the conversion graph. The recipe adapter maps the engine's records
onto the reference models, and the renderer imports the shared patterns directly. There is now a
single source of truth for Cooklang syntax.

---

## KI-15 — No schema-generation pipeline

**Severity:** Medium
**Status:** Open

### Symptom
`schemas/*.json` are hand-maintained and validated by tests, but Pydantic v2 can generate them. There
is no generation step, so the JSON schemas and the models are two independent sources of truth.

### Evidence
* `grep -rn "model_json_schema" --include=*.py .` → **no matches** in `src/` or `tests/`.
* `tests/test_ingredients.py:197-223` and `tests/test_recipes.py:231-234` validate YAML against the **JSON schema files**; Pydantic validates independently at load.
* Diffing `Ingredient.model_json_schema()` against `schemas/ingredients.schema.json` shows the disk copy defines an extra top-level `Ingredient` entry — i.e. they are already structurally divergent.
* The YAML files reference the schema via `# yaml-language-server: $schema=...`, so editor tooling trusts the JSON; the runtime trusts Pydantic.

### Impact
A model change not mirrored in JSON means editors flag valid data and CI validates a stale contract —
or vice versa. Two validation paths that can disagree are worse than one.

### Proposed fix
Generate the JSON schemas from the Pydantic models via `model_json_schema()` in a small script, and
add a test asserting the committed files match freshly generated output (fail on drift). This keeps
editor tooling and runtime validation contractually identical.

---

## KI-16 — Dead variables in `renderer.py`; loss and batch totals never rendered

**Severity:** Low
**Status:** Open

### Symptom
Five values are computed in `render_recipe_card_html` and never used. As a consequence, cooking
loss and batch totals never reach the card — which is why KI-13's `-205%` goes unnoticed.

### Evidence
* `src/meal_prep/renderer.py:102-109` assigns `batch_macros`, `serv_cost`, `raw_g`, `loss`, `portion_g`.
* Verified: none are referenced later in the function (only `serv_macros`, `serv_cost`-adjacent fields, and `cat_label` are used).

### Impact
Dead code, plus a real information gap: the card cannot display batch totals or cooking loss, so the
anomaly in KI-13 is invisible in the primary user-facing artifact.

### Proposed fix
Either render them (add batch totals and a weight-change row to the card's stats grid — resolves the
visibility half of KI-13) or delete the unused locals. Recommendation: **render them**, since the data
is already computed and the card is the authoring skill's primary review surface.

---

## KI-17 — No `pyproject.toml` / dependency manifest

**Severity:** Low
**Status:** Open

### Symptom
There is no packaging or dependency manifest, yet the test suite has import-time third-party
requirements.

### Evidence
* No `pyproject.toml`, `setup.py`, `requirements.txt`, `tox.ini`, or `Makefile` at the repo root.
* `tests/test_ingredients.py:5` and `tests/test_recipes.py` import `jsonschema`; the codebase requires `pydantic` v2 and `PyYAML`.
* Environment observed: `pydantic 2.13.5`, `jsonschema 4.26.0`, `pytest 9.1.1`.
* Run instructions everywhere are `PYTHONPATH=src python3 -m pytest tests/`.

### Impact
The environment is not reproducible from the repository. A fresh clone cannot be set up without
guesswork, and the required Pydantic major version (v2 — the models are v2-only) is undocumented as a
constraint.

### Proposed fix
Add a minimal `pyproject.toml` declaring `pydantic>=2`, `PyYAML`, and an optional `dev` extra with
`pytest` and `jsonschema`. Optionally configure `[tool.pytest.ini_options] pythonpath = ["src"]` to
eliminate the `PYTHONPATH=src` prefix, and register the package so `pip install -e .` works.

---

## KI-18 — Documentation drift on counts and taxonomy

**Severity:** Low
**Status:** Open

### Symptom
Several documented counts and taxonomy members do not match the data.

### Evidence
* **"7 aisle files"** — `README.md:35`, `AGENTS.md:13`, `INGREDIENTS.md:3`. Actual: **6** (`ls data/ingredients/*.yaml`).
* **"Frozen" aisle** — `README.md` lists "Meat & Seafood, Produce, **Frozen**, Dairy & Refrigerated, Pantry, Spices, Bakery" under the aisle taxonomy. `data/aisles.yaml` has no `frozen` aisle; frozen items (`frozen-sweet-corn`, `frozen-green-peas`) live under `produce`.
* **"5 category folders"** — `README.md:36`. Only `modular_carb` and `modular_protein` exist; the other three exist only as `RecipeCategory` enum members with no recipes.
* **Contradiction:** `README.md` describes the ingredient catalog as "Partitioned into 7 aisle files", while the catalog is partitioned by the 6 files that actually exist.

### Impact
Trust erosion and confusion for new contributors and for the `meal-authoring` skill, which is
explicitly instructed to consult these documents as authoritative.

### Proposed fix
Correct the counts in all three documents and align the README's aisle list with `data/aisles.yaml`.
Consider stating the counts as "currently N" so they do not silently rot again. Cross-links to
`data/aisles.yaml` (as `README` already does for other files) are preferable to restating the list.

---

## KI-20 — Business logic and I/O live on Pydantic models

**Severity:** High
**Status:** In progress — `adapters/` extracted (I/O relocated); `services/` extraction pending

### Symptom
Pydantic models carry behaviour that needs collaborators (registries, the conversion graph, other
models) or does I/O — in violation of the **model-purity rule** adopted in `AGENTS.md`: a model may
own logic that is a pure function of its own fields, and must not own logic that requires
collaborators.

### Evidence (audit)

**Needs a collaborator → should be a service (still pending):**

| member | needs | note |
| :--- | :--- | :--- |
| `Ingredient.price_per_100g/price_per_kg/price_per_unit` (`ingredient.py:177-190`) | conversion graph, price | lazily builds a graph |
| `Ingredient.get_conversion_graph/can_convert/convert/container_weight_g` (`ingredient.py:191-229`) | `UnitsRegistry`, graph | orchestration + cache |
| `_build_ingredient_graph` / `_authored_endpoints` (`ingredient.py:232-286`) | `UnitsRegistry` | domain adapter, not a model |
| `Recipe.portion_cooked_weight_g` + `compute_*` (`recipe.py:77-187`) | `catalog`, `UnitsRegistry` | KI-01 duplicate of `calculator` |

**Does I/O → should be an adapter (resolved — moved to `adapters/`):**

| member | now lives at |
| :--- | :--- |
| `load_ingredients_file` / `load_all_ingredients` | `adapters/ingredients.py` |
| `parse_cooklang_body` / `split_recipe_file` / `load_recipe_file` / `load_all_recipes` | `adapters/recipes.py` |
| `load_units` / `get_default_units` | `adapters/units.py` |
| `load_aisles` | `adapters/aisles.py` |
| `load_equipment` | `adapters/equipment.py` |

**Known temporary edges (to be removed in the `services/` pass):**

Two lazy `from meal_prep.adapters.units import get_default_units` calls remain inside
`models/ingredient.py` (the dimension cross-check in `validate_conversions_uniqueness_and_dimensions`,
and the `container_weight_g` property). They are flagged `TODO(services)` and are the only two
`models → adapters` references in the codebase. Both are deleted when their call sites move behind a
conversion service.

**Presentation on models → should be presentation layer:**

| member | note |
| :--- | :--- |
| `PreparedRecipe.review_math()` / `IngredientBreakdown.detail_text` (`calculator.py`) | text formatting on a dataclass |
| `AislesConfig.to_cooklang_headers` (`aisle.py:54-56`) | Cooklang-specific output |
| `StorageType/RecipeCategory.display_name/description` (`enums.py`) | accepted minor (display label on enum) |

**Pure over own fields → OK to keep on the model:**

| member | why it stays |
| :--- | :--- |
| all `@field_validator` / `@model_validator` | data-shape validation |
| `AislesConfig.ordered_aisles/valid_ids/get` | pure lookup over own list |
| `EquipmentRegistry.normalize/get/is_valid/canonical_ids` | pure lookup over own items |
| `UnitsRegistry.normalize/dimension_of/to_base/convert/…` | pure function of `schema_data` (self-contained value object) |
| `DimensionGroup.canonical_units` | pure |

### Impact
The model package is the de facto home for three distinct concerns (data shape, business logic, I/O),
which is exactly the coupling the purity rule exists to prevent. It is the structural root of KI-01
(compute logic duplicated between `Recipe` and `calculator`), and it raises the cost of the planned
planner + shopping-list features, which are naturally services that would have to reach *through* the
models.

### Proposed fix
Introduce `services/` (business logic) and `adapters/` (I/O) packages; move members per the tables
above, taking models as arguments. See the architecture section of `AGENTS.md`. Resolve KI-01 in the
same pass (delete `Recipe.compute_*`; `calculator.prepare_recipe` is the single service).

**Progress:** the `adapters/` half is complete — all I/O moved out of `models/`, `models/__init__.py`
re-export surface trimmed to schemas, and the two flagged `models → adapters` lazy edges left as
explicit `TODO(services)` markers. The `services/` half (conversion orchestration, the KI-01
duplicate deletion, and presentation extraction) is the remaining work.

---

## KI-19 — Unused public API surface

**Severity:** Low
**Status:** Open

### Symptom
Some public methods and properties are never called outside their own definition.

### Evidence
* `AislesConfig.valid_ids` (`src/meal_prep/models/aisle.py`) — **0 references** (and exactly what KI-05 should use).

### Resolved in the conversion-graph refactor (KI-02 follow-up)
The conversion graph was rebuilt as a pure, immutable model; its dead/divergent public surface was removed:
* `ConversionGraph.reachable_units_from` → replaced by `reachable()` (returns `frozenset`).
* `ConversionGraph.all_units` → replaced by the `units` property (`frozenset`).
* `Ingredient.get_conversion_factor` → **deleted** (bypassed the graph and duplicated conversion logic; the stale-parallel risk to KI-01 is gone).
* `ConversionGraph.get_factor` / `conversion_map` / `normalize` / `container_weight_g` → folded into `factor()`, `factors` (read-only `Mapping`), and moved to the domain layer respectively.

### Impact
Only `valid_ids` remains as genuinely unused surface, and it has a planned consumer (KI-05).

### Proposed fix
Use `valid_ids` when resolving KI-05; remove it if KI-05 is resolved differently.

---

## Appendix — Verified correct (not issues)

For completeness, the following were checked and behave correctly:

* **Full test suite:** `54 passed in 1.53s` (`PYTHONPATH=src python3 -m pytest tests/`).
* **Layered architecture is genuinely acyclic:** `models/ → conversion_graph → calculator → library → renderer`, with `calculator` having no knowledge of HTML.
* **Transitive conversion closure:** BFS at load time with shortest-path selection gives O(1) lookups; spot-checked `olive-oil tsp->g = 4.6`, `kg->tbsp = 72.46`, `chicken pack->piece = 4.0`, and correctly returns `None` for `chicken cup->g` (no density bridge — appropriate).
* **Packaging consistency:** for all 28 ingredients, `container -> g` matches `container_weight_g` exactly (the sole anomaly is KI-12, which is a `unit -> g` mismatch, not a container mismatch).
* **Identity enforcement:** `id == file.stem`, `category == parent dir`, and `aisle == file stem` are all enforced at load.
* **Generated artifacts:** `recipe_cards/` is correctly gitignored and untracked; `.pytest_cache/` is equally untracked.
* **Duplicate detection:** global ingredient-ID and recipe-ID uniqueness are enforced across files.
* **Cost/weight math agreement between the two engines today** (see KI-01 — agreement is real, but unenforced).
