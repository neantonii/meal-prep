# Sanity Checks Reference

Two layers of warn-only challenges. The naive bands below are implemented by
`meal_prep.services.heuristics` (`check_ingredient`, taking a prepared
`Ingredient` and returning warning strings); the validator prints one `WARN`
line per warning. The USDA cross-check is agent reasoning over the FDC record
fetched in SKILL.md §1 — no script, no thresholds in code. The agent raises
each tripwire from either layer with the user and proceeds only on explicit
confirmation. Never silently accept, never fail the run on these alone.

## Macros: Atwater Energy Check

`kcal ≈ 4*protein + 4*(carbs − fiber) + 9*fat` (per-100g scaled; fiber
already inside `carbs` on Canadian labels — do not add it).

- Tolerance ±25 kcal. Beyond that, ask: "Label says X kcal but macros imply Y.
  Transcription error, or alcohol/polyols on the label?"
- Common cause: `sugars` double-counted into `carbs` is fine (subset, not
  additive).

## Macros: Sum Check

`protein + fat + carbs <= 105` g per 100 g.

- Above that, ask for re-transcription. Water makes most foods sum well below
  100; only pure oils/sugars approach it.
- Zero-macros salt/spices are legitimate (`kosher-salt`: all zeros except
  sodium). Confirm `sodium_mg > 1000` for salt, else challenge.

## Price Band

`price_per_100g = price / package_weight_g * 100`.

- Meat/seafood typical `2.00–6.00` CAD/100g; pantry `0.20–2.00`; spices
  `2.00–8.00` (small packs inflate this — confirm pack size, not price).
- Outside band: "This implies $X/100g. Confirm pack price $Y for Z g?"

## Shelf-Life vs Storage

| Storage | Plausible band |
|---|---|
| `ambient` | 7–1095 days (fresh garlic/lemon ~14–30, oils/grains/spices up to 1095) |
| `refrigerated` | 2–90 days (fresh meat 2–4, dairy up to 90) |
| `frozen` | 180–365 days |

- Fresh meat `> 7` days refrigerated: challenge (should be frozen or shorter).
- `frozen` with `< 30` days: challenge (freezer burn policy, not safety).
- `shelf_life_days` is how long the raw ingredient keeps before cooking.
  It does not limit a recipe's `fridge_days`, which is how long the
  cooked dish keeps (see the meal-recipe skill, §3).

## Conversion Plausibility

- `package -> g` should match the printed net weight within 5%. "Pack says
  454 g but edge gives 500 g — reweigh?"
- `count -> g` piece weight: chicken breast 150–300 g, eggs 50–70 g, garlic
  clove 2–5 g. Outside band, ask for reweigh.
- `cup -> g`: flour ~120, sugar ~200, rice ~185, frozen veg ~145. Density is
  ingredient-specific; challenge only on order-of-magnitude errors.

## Fetched Zeros

`fetch_product.py` lists every nutrient it reported as 0 under `zeros`:
the lookup turns a blank panel row into 0 even when told not to. Each one
is checked against the USDA record, scaled to the label's serving:

- It stands (`fetched`) when the USDA amount would also print as 0 under
  Canadian label rounding: fat, saturated fat, carbs, fibre, sugars and
  protein below 0.5 g; sodium and potassium below 5 mg. Example: frozen
  peas and carrots, USDA 0.4 g fat per 85 g, so a fetched "0 g" fat is
  plausible.
- Otherwise the USDA value replaces it (`usda`, green), and the read-back
  says so: "page lookup said 0 g fibre; USDA has 2.1 g per serving, so I
  used USDA".

## USDA Cross-Check

Compare the enriched per-100g macros against the FDC record fetched in
SKILL.md §1 (Foundation/SR Legacy values are already per 100 g — no basis
scaling). Read the record's `foodNutrients` yourself and decide which
numbers answer each macro field; there is no mapping table to follow.

- Panel and fetched entries: the label wins, USDA challenges. A large
  delta usually means a transcription or lookup error (re-check the
  source) or a genuinely different product (e.g. sweetened vs unsweetened,
  lean vs regular) — say which you suspect and wait. A small delta is manufacturing variance; confirm it
  stands and move on.
- No-label entries: USDA is the macro source, so there is nothing to
  compare against — instead, say why the picked record matches the food
  (description, dataType) and flag any judgment calls (closest available
  cut, cooked vs raw) for user sign-off.
- Branded records are noisy label data, not a reference: prefer
  Foundation/SR Legacy for the cross-check, and say so when the only
  available match is Branded.

## Challenge Script

For each tripwire, say what is weird, cite both numbers, propose the likely
fix, and wait:

> "Sanity flag: macros imply ~X kcal but the label says Y (Δ=Z). Usually a
> mistyped protein/fat. Want to re-check the label photo, or confirm Y stands?"

Record accepted warnings in the close-out report with reasons.
