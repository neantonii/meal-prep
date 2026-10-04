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

Invoke when ingredient authoring needs a USDA reference:

- No-label ingredients (fresh meat, produce, bakery): USDA is the macro
  source. Fetch the record, reason about the closest match, and stage the
  macros as `usda` provenance.
- Panel cross-check: a second opinion on transcribed label macros. The
  panel stays source of truth; USDA only challenges it.

Do not invoke for packaged foods with a readable panel unless the macros
look suspicious.

## Script

`scripts/usda_lookup.py` (stdlib only; reads `USDA_KEY` from the
environment):

```sh
python .agents/skills/meal-usda/scripts/usda_lookup.py search "<query>" [--limit N] [--data-types Foundation "SR Legacy"]
python .agents/skills/meal-usda/scripts/usda_lookup.py fetch <fdcId> [--out .agent_tmp/usda.json]
```

- `search` prints `totalHits` plus identity fields per hit (`fdcId`,
  `description`, `dataType`, `brandOwner`). Defaults to
  `--data-types Foundation "SR Legacy"` — baseline whole-food records.
  Pass `--data-types` empty to include Branded; expect noisy label data.
- `fetch` prints the full record verbatim (nutrients, portions, serving
  info), or writes it to `--out` for longer sessions.

## Flow

1. `search` with a plain-food query (`"<food> raw"`, `"<food>"`). Read
   the candidate list and pick the closest description + dataType
   yourself — the script ranks nothing.
2. `fetch` the pick. Read `foodNutrients` (each entry carries
   `nutrient.number`, `nutrient.name`, `nutrient.unitName`, `amount`) and
   decide which numbers answer the draft's macro fields. Foundation and
   SR Legacy values are per 100 g and compare directly against enriched
   per-100g macros.
3. Record the decision: cite the FDC ID (`fdcId`, description, dataType)
   in chat and in the close-out report. Staged USDA macros carry `usda`
   provenance and render green on the review card.
