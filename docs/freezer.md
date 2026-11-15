# Unassigned portions, freezing and the bin

Status: decided; not implemented. Changes several rules of
`docs/prep-sessions.md` (listed under "What changes in prep sessions");
that file is rewritten when this is built.

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
  `batches x servings`. There are no spare or unaccounted portions.
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
- Recipes cannot be dropped on the unassigned slot or the bin: a portion gets
  there only through a batch.
- The settled-meal lock applies to day slots as before: moving a settled
  meal anywhere needs Admin.
- There is no linking, relinking or unlinking of a single meal.

## Batches

- **Add:** only by creating a meal (table above).
- **Remove one batch:** from the session panel. It removes as many of that
  recipe's meals as one batch has portions, taken from the unassigned
  slot only. Refused when it holds fewer ("unassign 2 Beef chili meals
  first"); binned meals must be dragged back first. Removing the
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

Removing a recipe line or deleting a session directly goes away: both
happen when the last batch is removed.

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

- **Frozen meals** show a ❄ mark and their cook date wherever the meal is
  shown. When the dish does not freeze well the mark is a warning; nothing
  is blocked.
- **Unassigned:** its own section at the top of the recipe column. One row
  per recipe with the number of portions ("Beef chili x5"). Rows are
  dragged to days; meals are dropped on it. It makes no claim about what
  is physically frozen.
- **Bin:** a collapsed section under it with a count and the cost. It
  lists the meals binned in the last few days; older ones are behind
  "show older".
- **Recipe panel:** a recipe with unassigned portions shows how many, as a
  hint to take it from there.
- **Session panel:** each recipe row lists where its portions are (days,
  unassigned, bin) and has "remove a batch". Sessions accept one kind of
  drop: a recipe row from another session.
- The spare warning goes away.

## Storage

- `diary/slots.yaml` (`schemas/slots.schema.json`): two lists,
  `unassigned` and `bin`, of ordinary recipe entries (the week files' shape). `session`
  is required here; bin entries also carry `binned` (a date).
- Session items gain `fridge_days` and `freezer_friendly`.
- A spawned meal copies its title and numbers from the session's recipe
  line, so it is what was cooked, also after the recipe changes or is
  deleted.
- Multi-file edits keep the existing order (sessions, then meals, then
  deletions), extended with the slots file.

## Migration

Existing sessions have portions with no meal, which the principle forbids.
Migration 2 (`src/meal_prep/migrations/`) creates the missing meals, with
the numbers of the session's recipe line:

- for a session dated before the day it runs: in the bin, `binned` set to
  the session's date (so history does not show up as freshly binned);
- for a later session: unassigned.

It also fills `fridge_days` and `freezer_friendly` on existing session
items from the recipe library (left out when the recipe is gone: such
meals get no frozen flag). Bin costs for the
time before this release say little: some of those portions were eaten
without being logged.

## What changes in prep sessions

- **Batches are derived from linked meals** -> stored; changed only by
  adding or removing a batch.
- **Spare portions and their warning** -> gone; every portion is a meal.
- **Auto-link takes a free portion first** -> a recipe-panel drop always
  adds a batch to the cycle's session.
- **A drop that cannot link is saved unlinked** -> refused.
- **Manual links** (drop a meal on a session, link to a session day,
  unlink) -> gone; a recipe line moves as a whole.
- **A moved meal follows its cycle**, and is re-linked when the move
  breaks its link -> gone; a move never changes the session, and a day
  before the session's date is refused.
- **Remove an item, delete a session** -> remove a batch.
- **Admin skips batch recalculation and never grows a cooked session on a
  recipe drop** -> Admin only ignores settled and cooked.

## Out of scope

- Food that never came from a session (store-bought frozen meals, portions
  cooked before the app).
- A list of what is physically in the freezer today (derivable from the
  frozen flag; no new data needed).
- Cooking a recipe on the meal's own day when its cycle's session has
  already been cooked (an ad hoc session); such a drop is refused for now.
- Waste reports per week (the `binned` date is stored for them).
- Best-before warnings for portions frozen a long time.
