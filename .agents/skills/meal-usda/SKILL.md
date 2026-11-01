---
name: meal-usda
description: This skill should be used when the user asks to "look up USDA", "check FoodData Central", "find FDC macros for X", or mentions USDA validation, FDC ID, or no-label ingredient macros.
---

# USDA FoodData Central Lookup

Find the FoodData Central (FDC) record closest to an ingredient and read
its per-100 g macros. Picking the match and judging the numbers is agent
work; the commands below only fetch.

## When to Use

The meal-ingredient skill invokes this on every entry, in parallel with
label transcription. The record plays one of two roles:

- Panel entries: the panel stays source of truth; the record is the
  reference behind staging decisions and the cross-check in
  `meal-ingredient/references/sanity-checks.md`.
- No-label ingredients (fresh meat, produce, bakery): the record is the
  macro source, staged with `usda` provenance.

## Auth

The API key is an environment network secret: the proxy adds an
`X-Api-Key` header to requests to `api.nal.usda.gov`, so the commands
carry no key. A `403` with `API_KEY_MISSING` (or a refused connection)
means the secret or the allowed domain is not set up in this
environment — tell the user; do not hunt for a key.

## Commands

Search (Foundation and SR Legacy are the baseline whole-food records;
drop `dataType` to include noisy Branded label data):

```sh
curl -s -X POST https://api.nal.usda.gov/fdc/v1/foods/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"<food> raw","pageSize":8,"dataType":["Foundation","SR Legacy"]}' \
  | jq '{totalHits, foods: [.foods[] | {fdcId, description, dataType}]}'
```

Fetch one record's macros, keyed by the catalog's `macros` field names:

```sh
curl -s https://api.nal.usda.gov/fdc/v1/food/<fdcId> | jq '
  (reduce (.foodNutrients[] | select(.amount != null)) as $n
     ({}; .[$n.nutrient.number | tostring] = $n.amount)) as $a
  | {fdcId, description, dataType,
     calories_kcal: ($a["208"] // $a["958"] // $a["957"]),
     protein_g: $a["203"], fat_g: $a["204"], carbs_g: $a["205"],
     fiber_g: $a["291"], sugars_g: $a["269"], saturated_fat_g: $a["606"],
     sodium_mg: $a["307"], potassium_mg: $a["306"]}'
```

Nutrients are matched by FDC nutrient number, never by name (names vary:
SR Legacy says "Total Sugars", not "Sugars, total"). `null` means the
record does not report it. Energy: SR Legacy reports `208`; Foundation
records often only carry the Atwater energies (`958` specific factors,
then `957` general) — the fallback picks them in that order. Values are
per 100 g and compare directly with enriched per-100 g macros. Drop the
`jq` filter only when you need the full record (portions, serving info).

## Flow

1. Search with a plain-food query (`"<food> raw"`, `"<food>"`). Results
   are not ranked for you — read the list and pick the closest
   description; prefer SR Legacy (macro-complete) over Foundation (often
   a sparse analytical subset). If no same-food hit appears, re-query
   once with different wording.
2. Fetch the pick. If protein or energy is `null`, fetch the next-closest
   candidate, then stop and reason from the best record you have.
3. Cite the record (`fdcId`, description, dataType) in chat and in the
   close-out report.

Keep it tight: no re-running searches that already answered, no fetching
several candidates to compare.
