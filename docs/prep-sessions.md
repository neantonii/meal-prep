# Prep sessions

Status: decided; first version implemented. The week page layout is a trial,
to revisit after use.

## Goal

Plan and log meal prep sessions alongside the diary, and link each diary
entry to the session that produced it, so that what is prepped and what is
eaten stay aligned. Per-session ingredient lists build on this later.

## Out of scope

- Per-session required-ingredient / shopping list (next feature; the data it
  needs is already frozen, see "Session item").
- Free-form takeout / eating-out entries (#142) and AI macro estimates (#141).
  Every diary entry stays a recipe here; "no session" means a recipe entry
  that is not linked to any session.
- Checks that compare portions made with portions eaten (shortfall, waste,
  fridge life). Only the hard rules below are enforced.
- The PoC optimizer (`src/meal_prep/planner/`). `Recipe`, `MacrosInfo`,
  `RecipeCategory` and `Library` are unchanged; sessions are diary data, not
  part of `Library`.

## Session

- A prep session is a date plus a list of items. Sessions are **not tied to
  weeks**: a Sunday session typically feeds that Sunday's dinner and the start
  of the next week.
- At most one session per day. A session is saved once it has an item; the
  last item removed deletes it.
- Every session has a permanent id (UUID). Moving it to another day keeps the
  id, so entries linked to it are untouched.

## Session item

- A recipe, `batches` (how many times it is made as written; a whole
  number, default 1) and an `ad_hoc` flag.
- Portions = batches × servings. Both are whole numbers, so portions are
  exact; a recipe with fractional servings can't be added to a session.
- `ad_hoc` = cooked at mealtime rather than on prep day; its ingredients are
  still bought for this session. It changes no amount. Future batch-prep
  reports leave ad-hoc items out.
- One item per recipe in a session.
- **Frozen when added** (like diary entries, #107): title, servings per batch,
  per-serving cost and macros, and the per-batch ingredient lines (ingredient
  id, name, grams, cost). Changing `batches` keeps them; nothing is
  recomputed. To pick up a changed recipe, remove the item and add it again.

## Links

A diary entry has an optional `session` (the session id). A linked entry must
align with its session:

1. the session lists the entry's recipe;
2. the entry's date is on or after the session's date (same day allowed);
3. entries linked to an item never exceed its portions.

The server enforces these on every edit. Rules span weeks, so they are
checked across all weeks, not inside one week file.

## Editing modes

One diary, one stored state (no planned/eaten flag). The mode decides which
edits are allowed:

| Mode | When | Behaviour |
|---|---|---|
| **Plan** | days and sessions *after today* | Fill ahead of time; auto-fill keeps the rules true. |
| **Log** | *today and earlier* | Edit only where reality deviated; nothing is auto-filled. |
| **Admin** | header switch, off on reload | Amend history; rules still apply, nothing is auto-fixed. |

"Today" is the server's local date. An edit is checked against the mode of
every date it touches; if any is Log, Log rules apply (Admin overrides all).

### Entries

| Edit | Plan | Log | Admin |
|---|---|---|---|
| Add from the recipe palette | auto-linked (below) | unlinked | unlinked |
| Add from a session card | linked; auto-fill | refused | linked if the rules hold |
| Remove | ✅ | ✅ (frees the portion) | ✅ |
| Move / reorder | ✅; a broken link is re-linked (auto) | ✅ if the link still holds | ✅ if the link still holds |
| Link / unlink / change session | ✅; auto-fill | refused | ✅ if the rules hold |

**Auto-fill** (Plan only): linking an entry to a session that lacks its
recipe adds the item (1 batch); linking to a full item adds one batch. Only sessions that are themselves in Plan are changed; otherwise the link
is refused.

**Auto-link** (palette drop in Plan): the entry links to the first of

1. the latest session within the 7 days up to the entry's date that lists
   the recipe with a free portion;
2. the latest Plan date within those 7 days that has a session or is a
   default session day (Sun, Tue, Thu), auto-filled;

and stays unlinked if neither exists.

### Sessions

Domain rule: once food is prepared you may choose not to eat it, but you can
never retroactively make more.

| Edit | Plan | Log | Admin |
|---|---|---|---|
| Add an item | ✅ | refused | ✅ |
| Raise `batches` | ✅ | refused | ✅ |
| Lower `batches` / remove an item / delete the session | ✅ | ✅ | ✅ |
| Change `ad_hoc` | ✅ | ✅ | ✅ |
| Move to another day | ✅ (both days in Plan) | refused | ✅ |

Never allowed: lowering portions below the linked entries, removing an item
or deleting a session that has linked entries, moving a session after any of
its linked entries, or onto a day that already has a session.

## Week page

- A strip of one-line session chips above the grid (date, mode, "10 recipes
  · 17/24 eaten"): every session dated from the Sunday before the week
  through the week's own Sunday (typically Sun, Tue, Thu, Sun). A Sunday
  session shows in both weeks; it is one session.
- Clicking a chip opens that session's items in a full-width panel below the
  strip (one at a time); a session of ~10 recipes stays a few rows high.
- Empty placeholders fill the default days (Sun, Tue, Thu) in that range;
  "+ session" adds a placeholder on another day.
- Older sessions linked from this week's entries (e.g. frozen portions)
  appear as extra chips at the start.
- Each item shows "eaten/made" (linked entries in all weeks vs portions).
- Drop a palette recipe on a chip or the open panel to add an item; drag an
  item from the panel into a slot for a linked entry; drop a meal on a chip
  or the panel to relink it (same rules as any link).
- Entries show their source as a colored left edge (the session's color;
  unlinked entries have their own color). A date badge appears only for an
  unusual source: anything but the latest session strictly before the
  entry's day (a same-day session is unusual).

## Storage

- One YAML file per session: `diary/sessions/<YYYY-MM-DD>.yaml`
  (`schemas/session.schema.json`). It lives in the mounted `diary/` folder,
  so deploys need no change.
- Week files gain an optional `session` field per entry; every existing week
  file stays loadable.
- Multi-file edits write sessions before weeks and delete sessions last, so
  an interrupted edit can leave a spare portion but never break a rule.
- Maps to two linked tables if the diary moves to SQLite (#125).
