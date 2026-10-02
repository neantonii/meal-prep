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
- Collect via chat (in stages, one question group at a time) or via the HTML
  form below — never both half-done. The form replaces the staging, not the
  confirmation: every value still needs user sign-off.
- The form never validates. Its only backend is
  `scripts/validate_ingredient.py --stdin`; no domain check may live in the
  page. Errors block submit, warnings need explicit user acceptance — same as
  chat.
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

Record the basis exactly as printed. Enrichment scales to per-100g via the
conversion graph. Run the Atwater and macro-sum challenges from
`references/sanity-checks.md` before accepting.

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

For field shapes and worked examples (simple, custom-unit, count-chain), see
`references/ingredient-catalog.md`.

### 6. Draft, validate, challenge

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

### 7. Close out

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
- **`scripts/ingredient_form.py`** — generates the entry form from
  `schemas/ingredient.schema.json` (+ `data/aisles.yaml`, `data/units.yaml`).
  Regenerate, never hand-edit. Flow: user fills sections, clicks Validate to
  reveal the stdin payload, agent runs the validator, user pastes the JSON
  verdict back, page renders errors/warnings/derived and gates Submit on
  zero errors. Pre-fill macros from a label photo read-back when available.
- **`schemas/ingredient.schema.json`** (repo-level) — committed field schema
  generated from `IngredientDTO`. Read directly; refresh via
  `python scripts/refresh_schemas.py` when stale.
