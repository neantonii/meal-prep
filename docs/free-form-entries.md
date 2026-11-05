# Free-form diary entries (takeout, eating out)

Status: first version implemented (#142). AI estimates are next (#141).

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
screen) opens the form: a title with suggestions from your history as you
type, the whole order's kcal, protein, carbs, fat and cost (blank =
unknown), the share eaten (¼ to 2) and "a guess" (on by default; untick for
numbers from a menu or label). Clicking a free-form entry's title reopens
the form to correct it. Free-form entries have a dashed yellow edge.

## API

- `POST /api/diary/{week}/others`: `date`, `mealtime`, `position`, `title`,
  `kcal`, `protein_g`, `carbs_g`, `fat_g`, `fiber_g`, `cost` (the whole order;
  `null` = unknown), `portion` (default 1), `estimated`.
- `PUT /api/diary/{week}/others/{entry_id}`: the same fields without the
  placement; refused for recipe entries.
- `GET /api/usuals`: the repeats, as above.

Both edits are journaled (`other.add`, `other.edit`).

## Next: AI estimates (#141)

Gemini (a lite model, key in the host's environment) turns a messy
description into separate items, each with a clean name, brand, numbers,
source (published, typical or guess), assumptions and a calories range. A
brand mentioned once applies to the whole order. Without one, items are
generic and flagged where the brand matters. Values are for Canadian menus.
