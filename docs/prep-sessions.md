# Prep sessions

Status: implemented. How portions are kept track of (every portion is a
meal; the unassigned slot, the bin, the frozen mark) is in
`docs/freezer.md`; this file covers sessions, prep cycles, editing modes,
the week page and the ingredient list.

## Goal

Plan and log meal prep sessions alongside the diary, and tie each diary
meal to the session batch it is a portion of, so that what is prepped and
what is eaten stay aligned.

## Out of scope

- Subtracting counted stock from the ingredient list (inventory, see
  `docs/spikes/inventory.md`); the checklist below only records yes/no.
- Takeout / eating-out entries (#142, `docs/takeout.md`)
  and AI macro estimates (#141). They never belong to a session.
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
- At most one session per day. A session exists because it cooks
  something: putting a recipe on a day adds a batch to a session (creating
  it), and removing its last batch deletes it.
- Every session has a permanent id (UUID). Moving it to another day keeps the
  id, so its meals are untouched.

## Session item

- A recipe and `batches` (how many times it is made as written; a whole
  number).
- **Batches are stored, and change only by an explicit act**: a recipe put
  on a day adds one, "remove a batch" takes one away, and two lines of the
  same recipe merge when one is moved onto the other
  (`docs/freezer.md`, "Batches"). Nobody types them, and nothing
  recalculates them from the meals.
- Portions = batches × servings. Both are whole numbers, so portions are
  exact; a recipe with fractional servings can't be added to a session.
- "Made fresh, not prepped ahead" (e.g. salads) will be a recipe property,
  not a per-item choice (#145). Session files still carry an `ad_hoc` field;
  it is deprecated and ignored until then.
- One item per recipe in a session.
- **Frozen when added** (like diary entries, #107): title, servings per batch,
  per-serving cost and macros, how the cooked dish keeps (`fridge_days`,
  `freezer_friendly`), and the per-batch ingredient lines (ingredient
  id, name, grams, cost, aisle, and the retail package: product title, its
  authored size such as 4 l or 18 count, and packages per batch). More
  batches keep them; nothing is recomputed. The meals of its portions copy
  its numbers.
- Aisle values are stored, so they are never renamed or removed, only added
  (`Aisle` in `enums.py`). Lines frozen before aisles and packages were
  recorded have neither; migration 1 (`src/meal_prep/migrations/`) fills
  them in from the ingredient data on the first start after upgrading.
  Items saved before the keeping values were recorded have none: their
  meals get no frozen mark.

## Links

A recipe meal names its session (`session`, the session id) from the moment
it is created, and keeps it: a meal is one portion of that session's batch.
Only a whole recipe line moves to another session. A meal must align with
its session:

1. the session lists the meal's recipe;
2. a meal on a day is on or after the session's date;
3. the meals of an item (on days, unassigned and binned together) never
   exceed its portions.

The server enforces these on every edit. Rules span weeks, so they are
checked across all weeks and both slots, not inside one file.

Rule 3 is "never more", not "exactly": every edit keeps meals and portions
equal, but nothing breaks when a file has fewer meals (an interrupted edit,
a hand-edited file, a session from before portions were meals). The week
page shows such portions as a "spare" warning.

Recipe meals without a session exist in older week files; they stay as they
are, and no new ones can be created.

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
  settled meal (add, remove, move) needs Admin; the week page shows
  settled slots muted. The unassigned slot and the bin never settle.
- **Planned and cooked sessions.** A session dated today or later is
  planned: batches can be added, removed and moved. An earlier session is
  cooked: its batches are a fact. Its meals still move freely between
  days, the unassigned slot and the bin.

**Admin** (header switch, off on reload) ignores "settled" and "cooked":
every meal and every session behaves as if still planned. There is no other
Admin logic.

"Today" is the server's local date. The day's Plan / Log label (after today
/ today and earlier) is kept for display and for moving sessions.

### Meals

| Edit (meal not settled) | Result |
|---|---|
| Put a recipe on a day (recipe panel) | one more batch in the session on the meal's cycle day, created when the day has none: one portion on that day, the rest unassigned. Refused when that session is cooked. |
| Put a session's recipe row on a day | the same, in that session; the day must be on or after its date |
| Put an unassigned recipe on a day | one of its portions moves there (`docs/freezer.md`) |
| Move / reorder | ✅; the session never changes. A day before the session's date is refused. |
| Remove | the portion goes to the unassigned slot. Takeout, and a recipe meal without a session, is deleted. |

**A recipe from the recipe panel always cooks a new batch**, also when that
recipe has unassigned portions: using what exists is a drag from the
unassigned list. There is no way to link, relink or unlink a single meal.

**A drop on a day whose cycle session is already cooked is refused**: to eat
a recipe that session did not cook, take an unassigned portion, or use
Admin to record after the fact that it was cooked there. (Cooking it on the
meal's own day, an ad hoc session, is not built.)

### Sessions

Domain rule: once food is prepared you may choose not to eat it, but you can
never retroactively make more or less.

| Edit | Planned session | Cooked session | Admin |
|---|---|---|---|
| Add a batch (only by putting a recipe on a day) | ✅ | refused | ✅ |
| Remove a batch | ✅ | refused | ✅ |
| Move a recipe line to another session | ✅ (both planned) | refused | ✅ |
| Move to another day (API only; no UI) | ✅ (both days in Plan) | refused | ✅ |

Never allowed: more meals than portions, removing a batch whose portions
are still on days or in the bin, moving a recipe line or a session to after
one of its meals, or a session onto a day that already has one.

## Week page

- A strip of one-line session chips above the grid (date, mode, "3
  recipes"): every session dated from the Sunday before the week through
  the week's own Sunday (typically Sun, Tue, Thu, Sun). A Sunday session
  shows in both weeks; it is one session.
- Empty placeholders fill the default days (Sun, Tue, Thu) in that range;
  "+ session" (Admin mode only) adds a placeholder on another day.
- Older sessions that this week's meals are portions of (e.g. frozen
  portions) appear as extra chips at the start.
- Clicking a chip rolls the session out over the week table: one row per
  recipe with its batches, portions and where they are ("Mon lunch · Tue
  lunch · 2 unassigned · 1 binned"), and "− batch". It closes on ×, Esc or a
  click outside.
- A recipe row is dragged by its title: onto a day to cook one more batch
  in that session, onto another session's chip or open panel to move the
  whole line there (an empty placeholder day gets its session created).
  That is the only thing a session takes; recipes from the recipe panel go
  onto days.
- "⚠ 1 spare" on a row or chip: portions no meal accounts for. It appears
  only when something went wrong (see "Links").
- "Details →" opens the session's own page (`/?session=<id>`): totals
  (recipes, portions, cost, kcal, protein) and a table per recipe on the
  left, the ingredient list on the right (below on a phone).
- The unassigned list and the bin sit above the recipe panel
  (`docs/freezer.md`).
- Meals show their session as a colored left edge (meals without a session
  have their own color). Colors follow the four standard slots of the page,
  the same every week: Sunday before, Tuesday, Thursday, the week's Sunday;
  other days and older sessions get two more.
- A date badge appears only when the session is not one of the page's four
  standard ones (an extra-day or older session); the standard ones are
  told apart by color alone.
- A meal eaten later than its dish keeps in the fridge shows ❄ (it was
  frozen in between), or ⚠ when the dish does not freeze well.

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

## Storage

- One YAML file per session: `diary/sessions/<YYYY-MM-DD>.yaml`
  (`schemas/session.schema.json`). It lives in the mounted `diary/` folder,
  so deploys need no change.
- Week files have an optional `session` field per entry; every existing week
  file stays loadable.
- Portions on no day are in `diary/unassigned.yaml` and `diary/bin.yaml`
  (`docs/freezer.md`).
- Multi-file edits are ordered so that an interrupted one can lose a meal or
  leave a portion without one (a spare), but never leave more meals than
  portions: sessions that keep or gain portions first, then the meal files
  (those that lose meals before those that gain them), then sessions that
  lose portions; deleted sessions last.
- The shopping checklist adds an optional `have` map to session files
  (written only once used) and `diary/staples.yaml`; existing files need no
  migration.
- Maps to linked tables if the diary moves to SQLite (#125).
