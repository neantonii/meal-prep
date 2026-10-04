---
name: meal-usda
description: This skill should be used when the user asks to "look up USDA", "check FoodData Central", "find FDC macros for X", or mentions USDA validation, FDC ID, or no-label ingredient macros.
---

# USDA FoodData Central Lookup

Pull raw FoodData Central (FDC) records so the agent can reason about them.
The script fetches data only — no nutrient mapping, no DTO shaping, no
plausibility checks. Picking the match and interpreting the nutrients is
agent work, not script work.

## When to Use

The meal-ingredient skill invokes this on every entry, in parallel with
label transcription — not as a fallback. Two roles for the fetched record:

- Panel entries: the panel stays source of truth; the USDA record is the
  reasoning reference behind staging decisions and the cross-check in
  `meal-ingredient/references/sanity-checks.md`.
- No-label ingredients (fresh meat, produce, bakery): USDA is the macro
  source. Fetch the record, reason about the closest match, and stage the
  macros as `usda` provenance.

## Script

`scripts/usda_lookup.py` (stdlib only). Copy these invocations exactly —
the `USDA_KEY=...` prefix is the auth, not decoration. Never run a bare
command (it fails with `USDA_KEY is not set`), never `export` the key,
never probe the environment for it, never invent flags like `--api-key`
(the script takes none):

```sh
USDA_KEY="$USDA_KEY" python .agents/skills/meal-usda/scripts/usda_lookup.py search "<query>" [--limit N] [--data-types Foundation "SR Legacy"]
USDA_KEY="$USDA_KEY" python .agents/skills/meal-usda/scripts/usda_lookup.py fetch <fdcId> --macros [--out .agent_tmp/usda.json]
```

- `search` prints `totalHits` plus identity fields per hit (`fdcId`,
  `description`, `dataType`, `brandOwner`). Defaults to
  `--data-types Foundation "SR Legacy"` — baseline whole-food records.
  Pass `--data-types` empty to include Branded; expect noisy label data.
- `fetch --macros` prints identity plus macro nutrients only
  (energy, protein, fat, carbs, fiber, sugars, sodium, potassium,
  sat fat) — the numbers that answer the draft's macro fields. Omit the
  flag only when you need the full record (portions, serving info);
  never dump full JSON to hand-filter nutrients.

## Flow

Keep it tight, not precious — the API budget is ~2000 calls/day, so an
extra call with value is fine. What dies here is pointless thrash:
re-running searches that already answered, fetching three candidates to
compare, dumping full records to hand-filter nutrients.

1. `search` with a plain-food query (`"<food> raw"`, `"<food>"`), limit
   5–10. Read the candidate list and pick the closest description
   yourself — the script ranks nothing, so the right hit may sit at
   rank 5. Prefer SR Legacy (macro-complete) over Foundation (sometimes
   a sparse analytical subset with no energy/protein rows at all). If no
   same-food SR Legacy hit is in the list, re-query once with different
   wording.
2. `fetch` the pick with `--macros`. Foundation and SR Legacy values
   are per 100 g and compare directly against enriched per-100g macros.
   If the result has no energy/protein (sparse record), fetch the
   next-closest candidate — then stop and reason from the best record
   you have.
3. Record the decision: cite the FDC ID (`fdcId`, description, dataType)
   in chat and in the close-out report. Staged USDA macros carry `usda`
   provenance and render green on the review card.
