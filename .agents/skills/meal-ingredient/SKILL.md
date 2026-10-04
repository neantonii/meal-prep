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

- Guess every required value and flag it yellow. Panel-literal facts
  (nutrition, price, serving line) render white; everything staged by
  judgment (identity, storage, shelf life, edges) renders yellow for
  sign-off. Guessing there is the flow, not a violation.
- The review card IS the collection flow, not a step after it. Transcription
  in hand, stage the draft and render immediately — never interrogate the
  user for identity/storage/edges first. The user corrects guesses on the
  card; chat questions are only for genuine ambiguities the card cannot show
  (e.g. an unclear serving line, new-entry vs update-existing).
- The review card (`render_ingredient_review.py` at repo root) renders the
  staged draft as HTML next to the label photo: `python
  render_ingredient_review.py <draft.json> <photo> <out.html>`. It shapes
  the draft into an `IngredientDTO`, gates on `prepare_ingredient` (gram
  reachability), and renders strictly from validated fields — a DTO or
  enrichment failure renders errors instead of values. The page owns
  formatting only; no domain check may live in it. Always open it with
  `show_preview` the moment it renders — never report transcription results
  without the card beside them.
- Write YAML only. Never edit `src/`, `data/units.yaml`, `data/aisles.yaml`, or
  `data/equipment.yaml` from this flow.
- Challenge weird data (see `references/sanity-checks.md`). Warn, do not
  silently accept; proceed only on explicit user confirmation.
- Keep `name` vs `step_name` semantically distinct, never derived one from
  the other.

## Workflow

### 1. Transcribe the label

Ask the user to upload a picture of the Nutrition Facts panel (usually a
grocery-webpage screenshot — panel plus page context). Transcribe it with
the built-in `inspect_image_with_vision` tool (`image_index: 0` on the
latest user message) — never ask the user to transcribe what vision can
read. Use this prompt verbatim:

> This is a screenshot from a grocery webpage showing a food product.
> Transcribe the Nutrition Facts panel exactly as printed. Reply with ONLY
> a JSON object, no fences. Include macros (calories_kcal, protein_g,
> fat_g, carbs_g, fiber_g, saturated_fat_g, sugars_g, sodium_mg,
> potassium_mg), serving_text (the serving-size line VERBATIM as printed,
> e.g. 'Per 4 squares (40 g)' — copy the whole line, do not split it into
> parts), and page context: brand, product (page title as shown), price,
> pack_size if visible anywhere on the page. If NO Nutrition Facts panel
> visible, return no_label true with seen description. Never estimate;
> illegible values are null.

Vision transcribes the panel only: never ask it for `unit`/`amount`
(those are DTO terms — asking scatters panel pieces across slots). One
verbatim `serving_text` string in, mapping to `unit` + `amount` happens
agent-side below. Page-context fields (brand, product, price, pack) are
small visible judgments — a wrong pick shows on the card for sign-off.
Fall back to verbatim transcription only when no photo is available.

When the photo has no Nutrition Facts panel (fresh meat, produce, bakery —
no label to read), say so plainly and stop: show what the photo did contain
(product, weight, price if printed) and wait. The user either fills macros
manually from a reference source they name, or uploads a different image.
Never estimate macros silently; a sourced manual value gets challenged
against the sanity bands like any other.

Parse the answer as JSON. Expected keys: `brand`, `product`, `pack_size`,
`price`, `serving_text` (verbatim serving line), flat macro nutrients.
Missing/optional nutrients are `null` (not printed) — never 0 unless the
panel prints zero. Map `serving_text` to the DTO's `unit` + `amount`
yourself. If the line is ambiguous, quote the verbatim line at the user —
never a decomposed triple, which is not panel text.

### 2. Stage the draft and show the card

Transcription in hand, stage the full draft at once — no staged
questioning. Propose `id` (kebab-case slug; collision-check with `grep -rn
"id: <slug>" data/ingredients/`), `aisle`, `name` (Title Case verbose, copy
sibling style), `step_name` (lowercase concise), `storage`, `shelf_life_days`,
and conversion edges (§3), all as best guesses. The card also needs the
photo bytes on disk (vision reads from the message, the renderer reads a
file), so save it fresh every run — never reuse a stale file from
`.agent_tmp/`; use distinct names per run when juggling photos:

```sh
python .agents/skills/meal-ingredient/scripts/extract_chat_image.py .agent_tmp/label
python render_ingredient_review.py .agent_tmp/draft.json .agent_tmp/label.png .agent_tmp/review.html
```

The renderer embeds the photo as a data URI, so the HTML renders wherever
the preview opens. Pass the extracted file path (with its real extension,
as printed by the script); never a bare filename.
Open with `show_preview` the moment it renders.

Present the read-back with the card: panel-literal values (white) vs your
guesses (yellow), Atwater and macro-sum results, price-band flag. The
user corrects what's wrong on the card. Chat follow-ups are only for
genuine ambiguities: an unclear serving line, new-entry vs
update-existing, a price that needs confirming as paid vs shelf-tag.

Record the basis as `unit` + `amount` only — never a free-text label
passthrough. Enrichment scales to per-100g via the conversion graph.

Exercise discretion when the printed serving is a countable nobody cooks
with: keep the basis in grams and skip the custom unit. Chips "per 26 chips
(50 g)" stay `per 50 g` — no one measures chips in individual pieces, so a
`chip` unit would be dead weight. But oatmeal "per 1 packet (28 g)" becomes
`per 1 packet` with a `packet -> g` edge — packets are how the food is
portioned and cooked. The test is whether recipes would ever name the unit;
a countable that only exists on the panel is not a unit.

### 3. Author conversions

Propose edges as guesses on the card; confirm recipe units with the user
at review time (`cup, tbsp, count, piece, ...`). Author per
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

### 4. Review card contract

The card renders strictly from validated fields — no free text. Panel
literals render white, staged guesses (identity rows, `guessed_edges`
sidecar) render yellow. A DTO or enrichment failure renders errors
instead of values. Layout lives in `render_ingredient_review.py`; do not
re-specify it here.

### 5. Draft, validate, challenge

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

### 6. Close out

Run the repo gate per `AGENTS.md`, then report derived values:
`package_weight_g`, `price_per_100g`, per-100g macros. State which sanity
warnings were accepted and why.

## Additional Resources

### Reference Files

- **`references/ingredient-catalog.md`** — file placement and three
  exemplar entries (simple, custom-unit, count-chain).
- **`references/conversions.md`** — conversion authoring rules; engine
  contract lives in code (linked there).
- **`references/sanity-checks.md`** — warn-only challenges with bands and
  fix prompts.

### Scripts

- **`scripts/extract_chat_image.py`** — saves the latest user-attached
  chat image to disk for the review card (vision reads from the message;
  the renderer needs a file): `python scripts/extract_chat_image.py
  .agent_tmp/label` → saves `.agent_tmp/label.<fmt>`, prints path + bytes.
  Nonzero exit = no image found. Stdlib only; chat attachments never land
  on disk, so never search the filesystem for uploads.
- **`scripts/validate_ingredient.py`** — enrich one entry via the real
  pipeline and print `check_ingredient` warnings. Usage:
  `python scripts/validate_ingredient.py data/ingredients/<aisle>.yaml --id <slug>`.
- **`render_ingredient_review.py`** (repo root) — side-by-side review card:
  staged draft JSON + label photo in, standalone HTML out. Shapes the
  draft into an `IngredientDTO`, gates on `prepare_ingredient`, renders per
  the §4 contract. Draft JSON may carry an authoring-only `guessed_edges` sidecar
  (never passed to validation) for yellow edge highlighting.
- **`schemas/ingredient.schema.json`** (repo-level) — committed field schema
  generated from `IngredientDTO`. Read directly; refresh via
  `python scripts/refresh_schemas.py` when stale.
