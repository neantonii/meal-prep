# Free-form diary entries (takeout, eating out)

Status: implemented (#142, #141).

## Goal

Log meals that aren't recipes, such as takeout, eating out or a slice of
office cake, so day and week totals stop leaving them out. Their
ingredients are unknown; only the numbers (usually guessed) matter.

## Entries

- A free-form entry is a diary entry **without a recipe**: a title and its
  numbers for **one portion**, as for every entry. Calories, protein, carbs
  and fat are **required**; cost, fiber and the rest may be absent
  (unknown), and Gemini can't know a price. `estimate` is present when the
  numbers are a guess (`source: manual | ai`, optionally a calories range
  and the assumptions).
- It is **never linked to a prep session**: food that wasn't prepped. The
  format refuses a free-form entry with a session, and linking one (picker
  or a drop on a session chip) is refused with a message. Moving it never
  auto-links it.
- Only the settled-meal lock applies (`docs/prep-sessions.md`): a settled
  slot needs Admin, like every other edit.
- Its numbers stay editable (a corrected guess); recipe entries stay frozen.
- Format compatibility: `recipe` and the numbers became optional in the
  schema, but the format still requires every number on an entry with a
  recipe (and the four above on one without), so every existing week file
  loads unchanged and no migration is needed.

## Totals

A total that includes a guess reads `≈ 1,100 kcal` (day cell, week header and
the rendered week report); entries show `≈ 390`. Calories and macros are
never unknown, so they are always complete; a cost total that leaves an
unknown cost out reads `≥ $20.74`.

## Repeats ("usuals")

There is no separate store. `GET /api/usuals` scans the diary weeks for
free-form entries and keeps one per title (case and spacing ignored), with
its **latest** numbers, most recent first, then most eaten. Correcting an entry therefore corrects
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

Every row is editable: name, kcal, protein, carbs and fat (required; "Add"
stays off until they are in) and cost (optional), and "guess" (on for
estimates; untick for numbers from a menu or label). An AI row also shows its
calories range, the quantity it assumed, where the numbers come from (menu
values, typical or guess), what it assumed, and its question when something
you didn't say changes the numbers. "Add 4" saves every row as its own
entry, in order.

Clicking a free-form entry's title reopens the form for that entry alone, to
correct it. Free-form entries have a dashed yellow edge.

## AI estimates (#141)

`POST /api/estimate` (`server/estimate.py`) sends the description to an
OpenAI-compatible chat completions API, Gemini's by default, with a JSON
schema for the reply, using only the standard library.

The prompt has one rule instead of special cases: **list every part of the
meal, including parts the description only implies** (a "meal" implies a
drink), so you see each one and fix or delete it; and **ask** when something
you didn't say changes the numbers a lot (which drink, which brand, size,
raw or cooked weight, oil), while still giving a best estimate. Each item
comes back with:

- a short `name` with the brand when known, plus `brand` (a brand mentioned
  once applies to the whole order);
- `quantity` assumed, `kcal` with `kcal_low`/`kcal_high`, protein, carbs,
  fat, fiber;
- `source`: `published` (the brand's menu values for the configured
  country, Canada), `typical` or `guess`;
- `question`: one short question with what is at stake ("Which drink? A
  regular soda adds about 200 kcal."), or empty;
- `assumptions`: only those that change the numbers.

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
  `items`: each a `title`, `kcal`, `protein_g`, `carbs_g`, `fat_g`
  (required), `fiber_g` and `cost` (optional, `null` = unknown),
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
