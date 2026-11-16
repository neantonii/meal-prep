# Unassigned portions, freezing and the bin

Status: implemented (#197). Sessions, prep cycles and editing modes are in
`docs/prep-sessions.md`.

## Goal

Prep some meals, freeze some of the portions, use them later. Portions
that have no day yet are kept in one place and taken from there, also
while planning: once a recipe is in a session, its other portions are
dragged from the unassigned list instead of being looked up in the recipe
list again.

Two things are kept apart:

- **Unassigned** is a home: a portion with no day. It is stored.
- **Frozen** is a state of a meal between cooking and eating. It is a flag
  implied by dates, never stored and never set by hand.

## Principle: every portion is a meal

A batch is exactly its portions, and each portion is a meal with a home:
a day, the unassigned slot or the bin.

- For every recipe of every session, the meals linked to it equal
  `batches x servings`: every edit keeps it so.
- This is not checked as a hard rule. The one check is that an item never
  has more meals than portions, so nothing breaks when a file has fewer
  (an interrupted edit, a hand-edited file, a session from before portions
  were meals). The week page shows those as a "spare" warning: it means
  something went wrong.
- A recipe meal belongs to a session batch from the moment it is created,
  and it stays with that batch. Takeout is the only meal without one.
- A meal is never deleted on its own. It moves between homes; it only
  disappears when its batch is removed.
- `batches` is stored and changes only by an explicit act (adding or
  removing a batch, merging two recipe lines). Nothing is recalculated
  from the meals.

Recipe meals without a session exist in older week files. They stay as
they are (removing one deletes it), but no new ones can be created.

## The two slots without a date

**Unassigned.** Portions that exist (or will, for a planned session) and
have no day. It fills on its own only when a batch is added: the portions
that are not placed on a day appear here. After that it changes only by
hand. For an automatic planner it is the stock on hand at the start, and
where the portions it leaves over at the end of its horizon go.

**Bin.** Portions thrown away. A meal gets here only by an explicit drag.
It still counts toward its batch, so the record of what was cooked, and
what the waste cost, stays. A binned meal records the day it was binned.

Both are normal slots: meals are dragged in and out like on any day. A
meal in either keeps its session link and its numbers. Neither slot ever
settles.

## Meals

| Act | Result |
|---|---|
| Drop a recipe from the recipe panel on a day | Adds **one batch** to the session on the meal's cycle day (created if that day has none): one portion on that day, the rest unassigned. Refused when that session day has passed. |
| Drag a recipe row from a session panel to a day | The same, in that session. The day must be on or after the session's date. |
| Drag a recipe from the unassigned list to a day | Moves one of its unassigned meals there: the one from the latest session on or before that day. Refused when there is none. |
| Drag a meal to another day | Moves it; the session never changes. Refused when the day is before the session's date. |
| Remove a meal from a day | Moves it to the unassigned slot. |
| Drag a meal to the bin | Moves it there and records the date. |
| Drag a meal out of the bin | To the unassigned slot or a day; the bin date is cleared. |

- A drop from the recipe panel always cooks a new batch, also when that
  recipe has unassigned portions. Using what exists is always a drag from
  the unassigned list.
- A meal can also move to a day in another week (API; the week page only
  reaches its own days, so across weeks a meal goes through Unassigned).
- Recipes cannot be dropped on the unassigned slot or the bin: a portion gets
  there only through a batch.
- The settled-meal lock applies to day slots as before: moving a settled
  meal anywhere needs Admin.
- There is no linking, relinking or unlinking of a single meal.

## Batches

- **Add:** only by creating a meal (table above).
- **Remove one batch:** from the session panel. The meals the recipe no
  longer has portions for are taken from the unassigned slot only. Refused
  when the meals on days and in the bin don't fit in what is left ("move 2
  to unassigned first"); binned meals must be dragged back first. Removing
  the
  last batch removes the recipe from the session, and a session without
  recipes is deleted. This is the only way a meal disappears.
- **Move a recipe to another session:** drag its row from a session panel
  onto another session, or onto an empty session day (which creates the
  session). The whole line moves, with all its batches and all its meals
  wherever they are. Refused when a day meal is before the new date. When
  the target already has the recipe, the lines merge and the batches add
  up. Shopping ticks for the recipe move with it.
- **Cooked sessions** (dated before today) are facts: adding, removing or
  moving a batch needs Admin. Their meals still move freely between days,
  the unassigned slot and the bin.

A recipe line or a session is never deleted directly: both go when the last
batch is removed.

## Admin

Admin ignores "settled" and "cooked": every meal and every session behaves
as if still planned. There is no other Admin logic. In particular a
recipe-panel drop on a past day adds the batch to that cycle's cooked
session (to record after the fact that something was cooked), and its
other portions are unassigned.

## Frozen

A meal has one of two lives: cooked, kept in the fridge, eaten; or cooked,
frozen, eaten. Which one is a flag on the meal, implied by dates:

- A meal on a day is **frozen** when that day is more days after its
  session's date than the dish keeps in the fridge.
- Unassigned and binned meals have no flag.

The session's recipe line stores the two values this needs when the recipe
is added: `fridge_days` and `freezer_friendly` (both from the recipe's
`storage` block). Sessions get no other new behaviour.

A plan that cooks on one Sunday and eats on the next is therefore just a
meal on the second Sunday linked to the first Sunday's session; the flag
says it was frozen in between. An automatic planner's solution is written
the same way: sessions with batch counts, meals on days, leftovers
unassigned.

## Week page

- **Frozen meals** show ❄ and their cook date wherever the meal is on a
  day. When the dish does not freeze well the mark is ⚠ instead; nothing
  is blocked.
- **Unassigned:** its own section above the recipe panel. One row per
  recipe with the number of portions ("Beef chili ×5"; ⚠ when the dish
  does not freeze well). Rows are dragged to days or to the bin; meals are
  dropped on it. It makes no claim about what is physically frozen.
- **Bin:** a collapsed section under it with a count and the cost. It
  lists the meals binned in the last three days; older ones are behind
  "show older". A binned meal is dragged back to a day or to Unassigned.
- **Session panel:** each recipe row lists where its portions are (days,
  unassigned, bin) and has "− batch". Sessions accept one kind of drop: a
  recipe row from another session.

## Storage

- `diary/unassigned.yaml` (`schemas/unassigned.schema.json`) and
  `diary/bin.yaml` (`schemas/bin.schema.json`): each a list `meals` of
  ordinary recipe entries (the week files' shape). `session` is required
  here; bin entries also carry `binned` (a date). A missing file is an
  empty slot.
- Session items gain `fridge_days` and `freezer_friendly`, both optional.
- A spawned meal copies its title and numbers from the session's recipe
  line, so it is what was cooked, also after the recipe changes or is
  deleted.
- The write order of a multi-file edit is in `docs/prep-sessions.md`
  ("Storage").

## Existing diaries

No migration. Nothing is created for sessions that already exist:

- both slots start empty, so portions cooked before this release never
  appear in the unassigned list;
- their recipe lines show the portions no meal accounts for as "spare";
- their items have no `fridge_days`, so meals from those batches get no
  frozen mark;
- meals that were linked by hand to older sessions keep their links.

## Out of scope

- Food that never came from a session (store-bought frozen meals, portions
  cooked before the app).
- A list of what is physically in the freezer today (derivable from the
  frozen flag; no new data needed).
- Cooking a recipe on the meal's own day when its cycle's session has
  already been cooked (an ad hoc session); such a drop is refused for now.
- A flag set by hand (or by a planner) to freeze a portion that will be
  eaten within its fridge life.
- Bringing portions cooked before this release into the unassigned list.
- Waste reports per week (the `binned` date is stored for them).
- Best-before warnings for portions frozen a long time.
