---
name: meal-ingredient
description: This skill should be used when the user asks to "add an ingredient", "new catalog entry", "add macros for X", "register a custom unit", "add conversions for X", or mentions ingredient catalog, data/ingredients, macros basis, or package weight.
---

# Meal Ingredient Authoring

Author one `data/ingredients/<aisle>.yaml` entry: identity, retail reference,
nutrition basis, and conversion edges. Enrichment derives pricing and per-100g
macros from these facts; validation proves gram reachability.

## When to Use

Invoke for a single new ingredient or a fix to an existing entry. For recipe
work invoking this skill, return to the recipe flow after the entry validates.
Do not batch multiple unrelated ingredients in one pass.

## Core Rules

- Never invent nutrition, price, or weights. Nutrition and price are
  user-supplied facts. Missing values stay `TODO(user)` until the user answers.
- Collect via chat (in stages, one question group at a time). Every value
  still needs user sign-off on the side-by-side review card before drafting.
- The review card (`render_ingredient_review.py` at repo root) renders a
  recognizer draft as HTML next to the label photo: `python
  render_ingredient_review.py <draft.json> <photo> <out.html>`. It shapes
  the draft into an `IngredientDTO`, gates on `prepare_ingredient` (gram
  reachability), and renders strictly from validated fields — a DTO or
  enrichment failure renders errors instead of values. The page owns
  formatting only; no domain check may live in it.
- Write YAML only. Never edit `src/`, `data/units.yaml`, `data/aisles.yaml`, or
  `data/equipment.yaml` from this flow.
- Challenge weird data (see `references/sanity-checks.md`). Warn, do not
  silently accept; proceed only on explicit user confirmation.
- Keep `name` vs `step_name` semantically distinct, never derived one from
  the other.

## Workflow

### 1. Identify the slot

Determine `id` (kebab-case slug) and `aisle` (one of `produce, bakery, meat,
seafood, dairy, pantry, spices`). Check for collisions:

```sh
grep -rn "id: <slug>" data/ingredients/
ls data/ingredients/<aisle>.yaml
```

Abort on duplicate id across any file. Confirm the target file is
`data/ingredients/<aisle>.yaml` — the `aisle` field must equal the file stem
(adapter-enforced).

### 2. Collect identity

Ask the user for:

- `name`: Label-style noun, Title Case, verbose
  (e.g. `Boneless, Skinless Chicken Breast`).
- `step_name`: Prose noun, lowercase, concise (e.g. `chicken breast`).
- `storage`: `ambient | refrigerated | frozen`.
- `shelf_life_days`: integer > 0 under that storage mode.

Copy casing/style from sibling rows in the same aisle file. Challenge
storage/shelf-life mismatches per `references/sanity-checks.md`.

### 3. Collect retail reference

Ask the user for the exact pack bought:

- `brand`, `product` (full commercial name), `price` (CAD, > 0).
- Pack net weight or count (needed for the `package` edge below).

Derive nothing. A guessed price corrupts `price_per_100g` and every recipe
cost plus planner totals.

### 4. Collect macros basis

Prefer a label photo over transcription: ask the user to upload a picture of
the Nutrition Facts panel. Read it with vision and pre-fill `unit` + `amount`
(the `per ...` basis, e.g. `per 55 g`, `per 1/3 cup`), required
`calories_kcal, protein_g, fat_g, carbs_g, fiber_g` (>= 0), and optional
`saturated_fat_g, sugars_g, sodium_mg, potassium_mg` when printed. Show every
read-back value to the user for confirmation before accepting — vision
misreads digits, and a wrong basis corrupts all per-100g macros. Fall back to
verbatim transcription when no photo is available.

When the photo has no Nutrition Facts panel (fresh meat, produce, bakery —
no label to read), say so plainly and stop: show what the photo did contain
(product, weight, price if printed) and wait. The user either fills macros
manually from a reference source they name, or uploads a different image.
Never estimate macros silently; a sourced manual value gets challenged
against the sanity bands like any other.

Record the basis as `unit` + `amount` only — never a free-text label
passthrough. The review card derives its subline (`per 1 packet (28 g)`)
from the validated DTO plus the conversion graph, so a recognizer's
`"label": "1 packet (28 g)"` string is garnish, not data. Enrichment scales
to per-100g via the conversion graph. Run the Atwater and macro-sum
challenges from `references/sanity-checks.md` before accepting.

Exercise discretion when the printed serving is a countable nobody cooks
with: keep the basis in grams and skip the custom unit. Chips "per 26 chips
(50 g)" stay `per 50 g` — no one measures chips in individual pieces, so a
`chip` unit would be dead weight. But oatmeal "per 1 packet (28 g)" becomes
`per 1 packet` with a `packet -> g` edge — packets are how the food is
portioned and cooked. The test is whether recipes would ever name the unit;
a countable that only exists on the panel is not a unit.

### 5. Collect conversions

Ask which units recipes will use (`cup, tbsp, count, piece, ...`), then ask
for one kitchen measurement per unit. Author edges per
`references/conversions.md`:

- Always author `package -> <unit>` with the weighed pack size.
- Author `<unit> -> g` for every unit used (including `count` when recipes use
  `@id{N}` with no unit, and every `custom_units` canonical).
- Author `macros basis -> g` when the basis is not already `g`.
- Register non-standard units under `custom_units` as
  `canonical: [canonical, plural, ...]` (canonical listed explicitly).
- Split panel facts from guesses into separate edges. When the panel gives a
  countable in volume (`1 can = 222 ml`), author that edge as printed, then
  bridge to grams with an explicit density edge (`ml -> g = 1`) rather than
  folding the guess into the panel edge (`can -> g = 222`). The guess stays
  visible and challengeable instead of hiding inside a white row.
- Provenance is authoring-only and never enters the DTO or catalog YAML.
  Track guesses in a sidecar list (`guessed_edges: [{from, to}]`) that the
  review report reads for yellow highlighting. When the draft graduates,
  either the user confirms the guess (edge becomes plain) or it gets weighed
  properly. `src/` and `data/ingredients/` never carry provenance fields.

For field shapes and worked examples (simple, custom-unit, count-chain), see
`references/ingredient-catalog.md`.

### 6. Review card layout

The card renders strictly from validated DTO fields — no free text. Layout:

- **Header**: slug (`dto.id`), name (`dto.name`), brand · product
  (`dto.reference.*`), price · package (`$X.XX` formatted float,
  `{factor} {to_unit}` from the `package` edge). Confidence colors apply
  here too: staged values render yellow, not white.
- **Nutrition**: macro tiles from `MacrosInfoDTO` with a derived subline
  `per {amount} {unit}` plus the graph-resolved gram equivalent in
  parentheses when the basis is not grams (`per 1 packet (28 g)` via
  `convert(amount, unit, "g")`; bare `per 50 g` when it is).
- **Details**: aisle/storage, shelf life, identity rows. No brand/product/
  price/package rows — those live in the header.
- **Conversions** (bottom): every authored edge as `1 {from} = {amount}
  {to}`, one row per edge, confidence-colored per edge (`guessed_edges`
  sidecar renders yellow). Empty when the draft has no edges.

### 7. Draft, validate, challenge

Draft the entry from `schemas/ingredient.schema.json` (the contract) and the
exemplar entries in `references/ingredient-catalog.md` (the shape). Append to
the aisle file in id-sorted position (match file convention). Then run:

```sh
python .agents/skills/meal-ingredient/scripts/validate_ingredient.py \
  data/ingredients/<aisle>.yaml --id <slug>
```

Fix `ValueError`s by correcting the draft, never by editing the validator.
Review every `WARN` line with the user; proceed only on explicit confirmation.
Re-run until no errors remain.

### 8. Close out

Run the repo gate per `AGENTS.md`:

```sh
python -m ruff check . --fix
python -m ruff format .
python -m mypy
python -m pytest -q
```

Report derived values: `package_weight_g`, `price_per_100g`, per-100g macros.
State which sanity warnings were accepted and why.

## Additional Resources

### Reference Files

- **`references/ingredient-catalog.md`** — field-by-field schema, naming
  rules, and three worked examples.
- **`references/conversions.md`** — graph invariants, required paths,
  custom-unit rules.
- **`references/sanity-checks.md`** — warn-only challenges with bands and
  fix prompts.

### Scripts

- **`scripts/validate_ingredient.py`** — thin scaffolding: enrich one entry
  via the real pipeline and print `check_ingredient` warnings. Usage:
  `python scripts/validate_ingredient.py data/ingredients/<aisle>.yaml --id <slug>`.
  With `--stdin` it reads one entry mapping (plus `aisle_file`) and prints a
  JSON verdict — the only backend the HTML form may call.
- **`render_ingredient_review.py`** (repo root) — side-by-side review card:
  recognizer draft JSON + label photo in, standalone HTML out. Shapes the
  draft into an `IngredientDTO`, gates on `prepare_ingredient`, renders per
  §6 layout. Draft JSON may carry an authoring-only `guessed_edges` sidecar
  (never passed to validation) for yellow edge highlighting.
- **`scripts/ingredient_form.py`** — legacy schema-driven entry form,
  superseded by the chat + review-card flow above.
- **`schemas/ingredient.schema.json`** (repo-level) — committed field schema
  generated from `IngredientDTO`. Read directly; refresh via
  `python scripts/refresh_schemas.py` when stale.
