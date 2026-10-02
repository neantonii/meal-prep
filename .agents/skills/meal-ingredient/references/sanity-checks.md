# Sanity Checks Reference

Warn-only challenges, implemented by `meal_prep.services.heuristics`
(`check_ingredient`, taking a prepared `Ingredient` and returning warning
strings). The validator prints one `WARN` line per warning; the agent raises
each with the user and proceeds only on explicit confirmation. Never silently
accept, never fail the run on these alone.

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
- Cross-check against the calling recipe: recipe `fridge_days` must be `<=`
  `min(ingredient shelf_life_days)`; flag chicken-breast-style smells
  (shelf 3 vs recipe 4).

## Conversion Plausibility

- `package -> g` should match the printed net weight within 5%. "Pack says
  454 g but edge gives 500 g — reweigh?"
- `count -> g` piece weight: chicken breast 150–300 g, eggs 50–70 g, garlic
  clove 2–5 g. Outside band, ask for reweigh.
- `cup -> g`: flour ~120, sugar ~200, rice ~185, frozen veg ~145. Density is
  ingredient-specific; challenge only on order-of-magnitude errors.

## Challenge Script

For each tripwire, say what is weird, cite both numbers, propose the likely
fix, and wait:

> "Sanity flag: macros imply ~X kcal but the label says Y (Δ=Z). Usually a
> mistyped protein/fat. Want to re-check the label photo, or confirm Y stands?"

Record accepted warnings in the close-out report with reasons.
