# Takeout diary entries

Status: implemented (#142, #141).

## Goal

Log meals that aren't recipes, such as takeout, eating out or someone
else's cooking, so day and week totals stop leaving them out. Their
ingredients are unknown; only the numbers matter, usually estimated.

## Entries: two types

A diary entry is one of two types, told apart by whether it names a recipe.
The file format has no `kind` field, so every existing week file loads
unchanged.

| | `RecipeEntryDTO` | `TakeoutEntryDTO` |
|---|---|---|
| `id`, `title` | ✓ | ✓ |
| `calories_kcal`, `protein_g`, `carbs_g`, `fat_g` | required | required |
| `recipe` | required | no such field |
| `cost`, `fiber_g` and the minor nutrients | required | optional (absent = unknown) |
| `session` | optional | no such field: takeout never links to a prep session |

The model layer mirrors this (`RecipeLogEntry`, `TakeoutLogEntry`), as do the
API (`kind: "recipe" | "takeout"`) and the UI types. Code that needs a recipe
or a session checks the type, and mypy and TypeScript enforce that.

- A takeout entry is **one portion**, like every entry.
- In sums, an unknown cost or minor nutrient counts as 0. Calories and macros
  are always known, so those totals are complete.
- A takeout entry's numbers stay editable, for a corrected estimate; recipe
  entries stay frozen (#107).
- Only the settled-meal lock applies (`docs/prep-sessions.md`): a settled
  slot needs Admin, like every other edit.
- Whether a number was estimated is not stored. The estimate matters while
  reviewing the form; once saved, it is just the entry's number.

## Repeats

There is no separate store. `GET /api/usuals` scans the diary weeks for
takeout entries and keeps one per title (case and spacing ignored), with its
latest numbers, most recent first, then most eaten. Correcting an entry
therefore corrects the next repeat.

Each item is its own entry ("McDonald's McChicken", "McDonald's Small
Fries"), so a repeat brings back just that item, not the whole order.

## UI

"+ other" in each open meal slot (it shows on hover; always on a touch
screen) opens the takeout form. It adds a whole order at once:

1. **Describe it**, messy is fine ("mcdonalds meal, mcchicken, small fries,
   6 nuggets + sweet and sour"), and press Estimate (or Ctrl/⌘+Enter). Each
   item comes back as its own row. Estimating again replaces those rows.
2. **Add a meal you had before**: type to search your history; a pick adds
   its row.
3. **+ type an item**: a blank row.

Every row is editable: name, kcal, protein, carbs and fat (required; "Add"
stays off until they are in) and cost (optional). An AI row also shows, while
you review, its calories range, the quantity, where the numbers come from
(menu values, typical or guess), what it assumed, and its question when
something you didn't say changes the numbers. None of that is saved. "Add 4"
saves every row as its own entry, in order.

Clicking a takeout entry's title reopens the form for that entry alone, to
correct it. Takeout entries have a dashed yellow edge.

## AI estimates (#141)

`POST /api/estimate` (`server/estimate.py`) sends the description to an
OpenAI-compatible chat completions API, Gemini's by default, with a JSON
schema for the reply, using only the standard library.

The prompt treats the order as **menu items** and has one general rule
instead of special cases: **list every part of the meal, including parts the
description only implies** (a "meal" implies a drink), so you see each one
and fix or delete it; and **ask** when something you didn't say changes the
numbers a lot (which drink, which brand, size, oil), while still giving a
best estimate. Everything is taken as eaten as served. Each item comes back
with:

- `name`: the item as a menu would list it: brand, then size or count when
  it changes the numbers, then the dish ("McDonald's 6 Chicken McNuggets"),
  so a 9-piece order is a different item and a different repeat. Names keep
  what you said and add nothing you didn't. `brand` too (a brand mentioned
  once applies to the whole order);
- `quantity`, `kcal` with `kcal_low`/`kcal_high`, protein, carbs, fat, fiber;
- `source`: `published` (the brand's menu values for the configured
  country, Canada), `typical` or `guess`;
- `question`: one short question with what is at stake ("Which drink? A
  regular soda adds about 200 kcal."), or empty;
- `assumptions`: only those that change the numbers.

Replies are cached in memory by description (case and spacing ignored), so
asking twice costs one call. A failed or malformed reply shows a message and
nothing is filled in.

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

- `POST /api/diary/{week}/takeout`: `date`, `mealtime`, `position`, and
  `items`: each a `title`, `kcal`, `protein_g`, `carbs_g`, `fat_g`
  (required) and `cost` (optional).
- `PUT /api/diary/{week}/takeout/{entry_id}`: one item's fields; refused for
  recipe entries.
- `GET /api/usuals`: the repeats, as above.
- `GET /api/estimate`: whether estimates are on, and the model.
- `POST /api/estimate`: `{text}` -> `{items}` (503 when off, 502 when the
  service fails).
- Week page entries carry `kind`: `recipe` (with `recipe`, `card_url`,
  `session`, `fiber_g`, `cost`) or `takeout` (with `cost`, `null` when
  unknown).

Adds and edits are journaled (`takeout.add`, `takeout.edit`); estimates are
logged.
