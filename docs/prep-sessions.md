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
- At most one session per day. A session exists because meals are linked
  to it: linking a meal creates it (or adds the recipe as an item), and in
  Plan an item whose last meal goes is removed, a session with no items
  left deleted. Once its day arrives a session stays as it was (a record).
- Every session has a permanent id (UUID). Moving it to another day keeps the
  id, so entries linked to it are untouched.

## Session item

- A recipe and `batches` (how many times it is made as written; a whole
  number).
- **Batches are derived, not typed.** In Plan they follow the linked meals:
  the fewest whole batches that cover them; every edit recalculates them,
  up or down. Once the session's day arrives they stay as they were, a record
  of what was made. Only Admin sets them by hand (corrections; a Plan
  session's batches follow its meals again on the next non-Admin edit).
- Portions = batches × servings. Both are whole numbers, so portions are
  exact; a recipe with fractional servings can't be added to a session.
- "Made fresh, not prepped ahead" (e.g. salads) will be a recipe property,
  not a per-item choice (#145). Session files still carry an `ad_hoc` field;
  it is deprecated and ignored until then.
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
| Remove | ✅ (the session shrinks to fit) | ✅ (the portion stays made: spare) | ✅ |
| Move / reorder | ✅; a broken link is re-linked (auto) | ✅ if the link still holds | ✅ if the link still holds |
| Link / unlink / change session | ✅; auto-fill | refused | ✅ if the rules hold |

**Auto-fill** (Plan only): linking an entry to a session that lacks its
recipe adds the item; its batches then follow the meals (see "Session
item"). Only sessions that are themselves in Plan are changed; otherwise the
link is refused.

**Auto-link** (palette drop in Plan): the entry links to the first of

1. the latest session within the 7 days before the entry's day that lists
   the recipe with a free portion;
2. the latest Plan date within those 7 days that has a session or is a
   default session day (Sun, Tue, Thu), auto-filled;

and stays unlinked if neither exists. The entry's own day never counts: a
meal rarely comes from that day's own prep, so a same-day source only
happens when chosen on purpose (dragging that session's item).

### Sessions

Domain rule: once food is prepared you may choose not to eat it, but you can
never retroactively make more.

| Edit | Plan | Log | Admin |
|---|---|---|---|
| Add an item (only by linking a meal) | ✅ | refused | ✅ |
| Set `batches` | derived from meals | refused | ✅ |
| Remove an item / delete the session | ✅ | ✅ | ✅ |
| Move to another day (API only; no UI) | ✅ (both days in Plan) | refused | ✅ |

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
  "+ session" (Admin mode only) adds a placeholder on another day.
- Older sessions linked from this week's entries (e.g. frozen portions)
  appear as extra chips at the start.
- Each item shows its batches ("2 batches") and, when the batch is
  underused, a warning ("⚠ 1 spare": portions made but not linked to a
  meal); chips sum the spare portions of their session.
- Sessions only take meals: drop a meal on a chip or the open panel to
  relink it (same rules as any link); on an empty placeholder day this
  creates the session with the meal's recipe. Palette recipes go into slots
  only (auto-link fills sessions); drag an item from the open panel into a
  slot for a linked entry.
- Entries show their source as a colored left edge (the session's color;
  unlinked entries have their own color). Colors follow the four standard
  slots of the page, the same every week: Sunday before, Tuesday, Thursday,
  the week's Sunday; other days and older sessions get two more.
- A date badge appears only when the source is not one of the page's four
  standard sessions (an extra-day or older session); the standard ones are
  told apart by color alone.

## Storage

- One YAML file per session: `diary/sessions/<YYYY-MM-DD>.yaml`
  (`schemas/session.schema.json`). It lives in the mounted `diary/` folder,
  so deploys need no change.
- Week files gain an optional `session` field per entry; every existing week
  file stays loadable.
- Multi-file edits write sessions before weeks and delete sessions last, so
  an interrupted edit can leave a spare portion but never break a rule.
- Maps to two linked tables if the diary moves to SQLite (#125).
