# Free-form diary entries (takeout, eating out)

Status: implemented (#142, #141).

## Goal

Log meals that aren't recipes, such as takeout, eating out or a slice of
office cake, so day and week totals stop leaving them out. Their
ingredients are unknown; only the numbers (usually guessed) matter.

## Entries

- A free-form entry is a diary entry **without a recipe**: a title, the
  numbers known for what was eaten (`cost`, `calories_kcal`, `protein_g`, …;
  absent = unknown), `portion` (the share of the order eaten, absent = all
  of it) and `estimate` (present when the numbers are a guess:
  `source: manual | ai`, optionally a calories range and the assumptions).
- It is **never linked to a prep session**: food that wasn't prepped. The
  format refuses a free-form entry with a session, and linking one (picker
  or a drop on a session chip) is refused with a message. Moving it never
  auto-links it.
- Only the settled-meal lock applies (`docs/prep-sessions.md`): a settled
  slot needs Admin, like every other edit.
- Its numbers stay editable (a corrected guess); recipe entries stay frozen.
- Format compatibility: `recipe` and the numbers became optional, but the
  format still requires every number on an entry with a recipe, so every
  existing week file loads unchanged and no migration is needed.

## Totals

Unknown numbers count as 0. A total that leaves one out reads `≥ 1,100 kcal`;
one that includes a guess reads `≈ 1,100 kcal` (day cell, week header and
the rendered week report). Entries show `≈ 390` for a guess and `?` for
unknown calories.

## Repeats ("usuals")

There is no separate store. `GET /api/usuals` scans the diary weeks for
free-form entries and keeps one per title (case and spacing ignored), with
its **latest** numbers scaled back to the whole order (numbers ÷ portion),
most recent first, then most eaten. Correcting an entry therefore corrects
the next repeat. A meal you no longer want suggested sinks down the list;
pinning or hiding suggestions would need a small `diary/usuals.yaml`
later.

Each item is its own entry (`McDonald's McChicken`, `McDonald's Small
Fries`), so a repeat brings back just that item, not the whole order.

## UI

"+ other" in each open meal slot (it shows on hover; always on a touch
screen) opens the takeout form. It adds a whole order at once:

1. **Describe it**, messy is fine ("mcdonalds meal, mcchicken, small fries,
   6 nuggets + sweet and sour"), and press Estimate (or Ctrl/⌘+Enter). Each
   item comes back as its own row (below). Estimating again replaces those
   rows.
2. **Add a meal you had before**: type to search your history; a pick adds
   its row with its latest numbers.
3. **+ type an item**: a blank row.

Every row is editable: name, kcal, protein, carbs, fat and cost for the
whole item (blank = unknown), the share eaten (¼ to 2) and "guess" (on for
estimates; untick for numbers from a menu or label). An AI row also shows its
calories range, the quantity it assumed, where the numbers come from (menu
values, typical or guess) and what it assumed. "brand?" marks an item whose
numbers depend on a brand or place nobody named. "Add 4" saves every row as
its own entry, in order.

Clicking a free-form entry's title reopens the form for that entry alone, to
correct it. Free-form entries have a dashed yellow edge.

## AI estimates (#141)

`POST /api/estimate` (`server/estimate.py`) sends the description to an
OpenAI-compatible chat completions API, Gemini's by default, with a JSON
schema for the reply, using only the standard library. Each item comes back
with:

- a clean `name` that includes the brand, plus `brand`;
- `brand_unclear`: no brand was given but the numbers depend on it (fries,
  burgers, coffee drinks, beer);
- `quantity` assumed, `kcal` with `kcal_low`/`kcal_high`, protein, carbs,
  fat, fiber;
- `source`: `published` (the brand's menu values), `typical` or `guess`;
- `assumptions`: raw vs cooked weight, oil, drink included or not, which
  product a vague name means.

A brand mentioned once applies to the whole order. Values are for the
configured country's menus (Canada). Weights without "raw" or "cooked" are
taken as raw for meat and fish and cooked for grains, and the reply says so.

Saved AI items keep `estimate: {source: ai, kcal_low, kcal_high,
assumptions}` in the week file. Replies are cached in memory by description
(case and spacing ignored), so asking twice costs one call. A failed or
malformed reply shows a message and nothing is filled in.

Configuration (the host's environment; see `compose.example.yml`):

| Variable | Default | |
|---|---|---|
| `GEMINI_API_KEY` (or `MEAL_PREP_ESTIMATE_KEY`) | none | without it estimates are off and the button hidden |
| `MEAL_PREP_ESTIMATE_MODEL` | `gemini-3.5-flash-lite` | any model the endpoint serves |
| `MEAL_PREP_ESTIMATE_URL` | Gemini's OpenAI-compatible endpoint | any OpenAI-compatible chat completions URL |
| `MEAL_PREP_ESTIMATE_COUNTRY` | `Canada` | whose menus to assume |

Descriptions leave the host for the provider. A free-tier Gemini key lets
Google use prompts to improve its products; a paid key doesn't.

## API

- `POST /api/diary/{week}/others`: `date`, `mealtime`, `position`, and
  `items`: each a `title`, the whole item's `kcal`, `protein_g`, `carbs_g`,
  `fat_g`, `fiber_g`, `cost` (`null` = unknown), `portion` (default 1),
  `estimated`, and for a guess `source` (`manual`/`ai`), `kcal_low`,
  `kcal_high`, `assumptions`.
- `PUT /api/diary/{week}/others/{entry_id}`: one item's fields; refused for
  recipe entries.
- `GET /api/usuals`: the repeats, as above.
- `GET /api/estimate`: whether estimates are on, and the model.
- `POST /api/estimate`: `{text}` -> `{items}` (503 when off, 502 when the
  service fails).

Adds and edits are journaled (`other.add`, `other.edit`); estimates are
logged.
