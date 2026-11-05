# Prep sessions

Status: decided; first version implemented. The week page layout is a trial,
to revisit after use.

## Goal

Plan and log meal prep sessions alongside the diary, and link each diary
entry to the session that produced it, so that what is prepped and what is
eaten stay aligned. Per-session ingredient lists build on this later.

## Out of scope

- Subtracting counted stock from the ingredient list (inventory, see
  `docs/spikes/inventory.md`); the checklist below only records yes/no.
- Free-form takeout / eating-out entries (#142) and AI macro estimates (#141).
  Every diary entry stays a recipe here; "no session" means a recipe entry
  that is not linked to any session.
- Checks that compare portions made with portions eaten (shortfall, waste,
  fridge life). Only the hard rules below are enforced.
- The PoC optimizer (`src/meal_prep/planner/`). `Recipe`, `MacrosInfo`,
  `RecipeCategory` and `Library` are unchanged; sessions are diary data, not
  part of `Library`.

## Session

- **A session is a supply cycle**: on its day the groceries arrive (in
  practice a delivery the same day) and the batch cooking happens, and it
  covers the meals until the next session. Every meal in that window belongs
  to it, cooked ahead or not (a salad made fresh on Friday still uses
  Thursday's delivery). One cycle yields two lists from the same meals: what
  to buy (every meal's ingredients) and what to cook (only recipes that are
  batch-cooked; "made fresh" becomes a recipe property, #145). Known edge
  cases, both for the future shopping list: a package often lasts more than
  one cycle (milk, cottage cheese: "make sure there is enough", i.e. needs
  minus stock on hand), and pantry staples such as coffee are never bought
  per cycle (see `docs/spikes/inventory.md`).
- A prep session is a date plus a list of items. Sessions are **not tied to
  weeks**: a Sunday session typically feeds that Sunday's dinner and the start
  of the next week.
- At most one session per day. A session exists because meals are linked
  to it: linking a meal creates it (or adds the recipe as an item), and
  while it is open (its day or later) an item whose last meal goes is
  removed, a session with no items left deleted. Once its day has passed a
  session stays as it was (a record).
- Every session has a permanent id (UUID). Moving it to another day keeps the
  id, so entries linked to it are untouched.

## Session item

- A recipe and `batches` (how many times it is made as written; a whole
  number).
- **Batches are derived, not typed.** While the session is open (its day or
  later) they follow the linked meals: the fewest whole batches that cover
  them; every edit recalculates them, up or down, on the session's own day
  too (it grows that day, so it must shrink back, or a mis-drop could never
  be undone). Once the day has passed they stay as they were, a record of
  what was made. Nobody types them, Admin included: a session grows by
  linking meals to it.
- Portions = batches × servings. Both are whole numbers, so portions are
  exact; a recipe with fractional servings can't be added to a session.
- "Made fresh, not prepped ahead" (e.g. salads) will be a recipe property,
  not a per-item choice (#145). Session files still carry an `ad_hoc` field;
  it is deprecated and ignored until then.
- One item per recipe in a session.
- **Frozen when added** (like diary entries, #107): title, servings per batch,
  per-serving cost and macros, and the per-batch ingredient lines (ingredient
  id, name, grams, cost, aisle, and the retail package: product title, its
  authored size such as 4 l or 18 count, and packages per batch). Changing
  `batches` keeps them; nothing is recomputed. To pick up a changed recipe,
  remove the item and add it again.
- Aisle values are stored, so they are never renamed or removed, only added
  (`Aisle` in `enums.py`). Lines frozen before aisles and packages were
  recorded have neither; migration 1 (`src/meal_prep/migrations/`) fills
  them in from the ingredient data on the first start after upgrading.

## Links

A diary entry has an optional `session` (the session id). A linked entry must
align with its session:

1. the session lists the entry's recipe;
2. the entry's date is on or after the session's date (a manual link may use
   the session's own day for any meal; auto-link only for dinner, below);
3. entries linked to an item never exceed its portions.

The server enforces these on every edit. Rules span weeks, so they are
checked across all weeks, not inside one week file.

## Editing modes

One diary, one stored state (no planned/eaten flag). Three ideas decide which
edits are allowed (#165):

- **Prep cycles.** The session days are the fixed preset **Sun, Tue, Thu**. A
  meal belongs to the latest session day on or before its day; the meal's
  own day counts only for **dinner and snacks**, eaten in the evening after
  that day's prep. Skipped preps and extra sessions are handled by hand.
- **Settled meals.** A cycle's meals lock **the day after the next session
  day**: on a Tuesday both Sunday's and Tuesday's cycles are open, and
  Sunday's locks on Wednesday. Today's meals never lock. Every edit to a
  settled meal (add, remove, move, link) needs Admin; the week page shows
  settled slots muted.
- **Open and closed sessions.** A session dated today or later is open: it
  grows to fit the meals linked to it, and shrinks back as they go. An
  earlier session is closed: it is the record of what was cooked, so it only
  gives free portions and never grows.

**Admin** (header switch, off on reload) edits settled meals and grows
closed sessions by hand. Nothing else differs, auto-link included.

"Today" is the server's local date. The day's Plan / Log label (after today
/ today and earlier) is kept for display and for moving sessions.

### Entries

| Edit (meal not settled) | Result |
|---|---|
| Add a recipe (palette drop) | auto-linked (below) |
| Add on a session card | linked to that session (manual link) |
| Remove | ✅; an open session shrinks to fit, a closed one keeps the portion (spare) |
| Move / reorder | ✅; re-linked by auto-link when the move breaks the link, or carries a meal into a later cycle while its own cycle's session is still open (below) |
| Link / unlink / change session | ✅ to any session on or before the meal's day (manual link) |

**A link only says where a portion went.** A manual link to an **open**
session adds the recipe or raises its batches as needed (see "Session item");
a **closed** session only gives a free portion, so a link to a full one, or
to one without the recipe, is refused ("full", "has no …"). Unlinking is
always allowed: the portion becomes spare.

**A moved meal follows its cycle** while nothing has been made for it: if
it was linked to its own cycle's session, that session is still open, and
the new slot belongs to a later cycle, auto-link re-links it there (the old
session shrinks). A manual link to another cycle's session, and a portion
of a closed session (already made), keep their link while it holds.

**Auto-link** runs on every drop, on any day, the same in Admin: it looks at
the session on the meal's cycle day, and links

1. to a free portion there;
2. else, while that day is open (today or later), to that session grown to
   fit, created when it doesn't exist yet;

and leaves the meal unlinked otherwise. An earlier cycle is never reached
into, however long its food keeps (a manual link may still pick it).

### Sessions

Domain rule: once food is prepared you may choose not to eat it, but you can
never retroactively make more.

| Edit | Plan | Log | Admin |
|---|---|---|---|
| Add an item (only by linking a meal) | ✅ | refused | ✅ |
| Set `batches` by hand | never (derived from meals) | never | never |
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
- Clicking a chip rolls the session out over the week table: one row per
  recipe with its batches, portions, the meals it feeds ("Mon lunch · Tue
  lunch") and any spare warning. It closes on ×, Esc or a click outside.
- "Details →" opens the session's own page (`/?session=<id>`): totals
  (recipes, portions, cost, kcal, protein) and a table per recipe on the
  left, the ingredient list on the right (below on a phone).

## Ingredient list

What to have on hand by the session: every item's frozen ingredient lines
times its batches (spare portions included: whole batches are cooked),
summed per ingredient. It is not a purchase list, since stock already at home
is not subtracted (that needs inventory).

- One table per aisle: packs of the frozen product (fractions included;
  "< 0.1" for a pinch), the ingredient with its product title, the pack size
  as authored (4 l, 18 pcs) and the cost. When the panel is narrow the pack
  size column is dropped; hovering a line always spells it out ("0.3 × 750 g
  pack · 225 g used · for …"), in case a product title is unclear.
- Grouped by aisle in walking order, each with its cost. Spices start
  collapsed (mostly staples); every other aisle is open. Lines without a
  frozen aisle or package (older files) come last, in grams.
- Computed by `PrepSession.needs()` (the model), so any client gets the same
  list.
- Clicking recipe rows on the left (several at once) narrows the list to
  their ingredients; a shared ingredient keeps its whole-session amount.

### Shopping checklist

Go through the list (or recipe by recipe) and tick what is at home; the rest
is the shopping list. Every tick can be undone the same way it was made.

- Ticks are per **recipe share**: each line's amount is the sum of the
  recipes using it, and each recipe's part can be ticked on its own.
  Stored on the session (`have`: recipe id -> ingredient ids); a session
  starts with nothing ticked. Allowed in every mode, since it records what
  is at home, not what was made or eaten.
- **Ticking a line** means "enough for every recipe that uses it": it ticks
  (or unticks) all its shares. A line with only some shares ticked shows as
  partly ticked; hovering a line lists each recipe's share and tick.
- **A recipe row** shows how many of its own shares are on hand ("3/5", ✓
  when all are). "have all" ticks only that recipe's shares; clicking the ✓
  unticks them again. A shared ingredient stays needed for the other
  recipes.
- **∞ (always)**: on hand in every session (oils, spices, sauces), all
  shares included; click it again to turn it off. Stored once in
  `diary/staples.yaml` (`always_have`, `schemas/staples.schema.json`), so it
  spans sessions; a new ingredient starts without it.
- **To buy**: the unticked shares (of the picked recipes, when some are
  picked), in whole packs (a started pack counts as one) with whole-pack
  costs; "copy as text" puts it on the clipboard.

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
- The shopping checklist adds an optional `have` map to session files
  (written only once used) and `diary/staples.yaml`; existing files need no
  migration.
- Maps to two linked tables if the diary moves to SQLite (#125).
