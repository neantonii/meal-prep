# Spike: inventory

Status: open question, nothing decided. No code changes come with this note.

## Question

Should the app know what food is on hand, and if so, which food and how?

Decisions so far: inventory comes later; no perishable leftovers; pantry
staples count as unlimited.

## Two kinds of "on hand"

- **Cooked portions.** A batch yields `servings`; what isn't eaten within
  `fridge_days` is waste unless the recipe is `freezer_friendly`. Frozen
  portions are real stock that outlives a week.
- **Raw remainders.** Ingredients are bought by the package
  (`package_weight_g`) but recipes use part of one. The rest lasts
  `shelf_life_days` at its `storage` temperature.

"No perishable leftovers" can mean either one, and both have different data.

## What exists today

- **Nothing tracks stock.** No inventory, purchase or shopping-list code.
- **Ingredients know their package and shelf life.** `price`,
  `package_weight_g`, `shelf_life_days`, `storage` (ambient / refrigerated /
  frozen) and `aisle` (produce, meat, seafood, dairy, pantry, spices).
- **Recipes know their batch life.** `servings`, `fridge_days`,
  `freezer_friendly`.
- **Cost ignores packages.** A recipe's cost is grams used × price per gram,
  so a half-used package costs half. Buying whole packages isn't modelled.
- **"Pantry staple" isn't defined.** The `pantry` and `spices` aisles and the
  `ambient` storage type are candidates, but nothing says "unlimited".

## Where ingredient history comes from (decided in #107)

Not from the diary. Batch cooking separates using ingredients (when a batch
is cooked) from eating (days later, possibly from the freezer), so stock
can't be derived from diary entries. Diary entries freeze only per-serving
numbers. Stock, if built, needs its own log of events recorded when they
happen, each frozen at write time:

- **Purchase:** ingredient, amount, price paid.
- **Cook session:** recipe, batch size, ingredient amounts used.

## Options

| | Model | For | Against |
|---|---|---|---|
| A | **Freezer only.** Track frozen cooked portions: added when a batch is frozen, removed when logged. | Small. The only stock that outlives a week. | Says nothing about raw ingredients. |
| B | **Derived, no stored state.** Compute "what should be left" from plan/diary vs. whole packages bought. | No manual counting. | Drifts from reality: spills, extra snacks, unplanned shopping. |
| C | **Stored stock.** An inventory file/table edited on purchase and use. | Matches reality when kept up. | Upkeep. Needs a place to live (ties to diary-in-a-database later). |
| D | **None.** Keep "no perishable leftovers" as a planning rule only. | Zero cost. | Freezer stock and waste stay invisible. |

## Open questions

1. **Which "on hand" matters:** cooked portions, raw remainders, or both?
2. **What is a staple?** By aisle (`pantry`, `spices`), by storage
   (`ambient`), or a per-ingredient flag?
3. **Source of truth:** counted by hand (C) or derived from plans and the
   diary (B)?
4. **Purchases:** should buying be recorded at all? It is the only place a
   real price paid would come from (relevant to frozen history, #107).
5. **Cost:** should cost switch to whole packages, or stay per gram?
6. **Where it lives:** YAML like reference data, or with the diary if that
   moves to a database?

## Smallest useful step, whatever the answer

A shopping list for a week: sum the plan's ingredients, round up to whole
packages, leave out staples. It needs no stored state, answers question 2 by
forcing a staple definition, and shows the raw remainders each week would
produce.

## Notes from prep sessions

Prep sessions are supply cycles (`docs/prep-sessions.md`): each session's
meals say what that cycle needs. Two observations for the shopping list
built on them:

- Packages often outlast a cycle (milk, cottage cheese), so a cycle's list
  is "make sure there is enough": needs minus stock on hand, rounded up to
  packages, not every ingredient bought fresh.
- Some items are never bought per cycle (coffee): a staple flag on the
  ingredient (question 2 above) keeps them off the list.
