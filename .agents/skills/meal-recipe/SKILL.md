---
name: meal-recipe
description: This skill should be used when the user asks to "add a recipe", "new recipe for X", "author a meal", "meal prep idea", or mentions recipe authoring, recipes/, .cook files, or cooking up a batch.
---

# Meal Recipe Authoring

Take a recipe idea to a validated `recipes/<category>/<slug>.cook` entry
with a rendered card: brainstorm or refine the idea, ground it in the
ingredient catalog (authoring what's missing), draft the Cooklang file,
validate, regenerate cards, and show the card.

## When to Use

Invoke for a new recipe or a rework of an existing one. Work on a feature
branch — ingredients and the recipe land in the same change tree. Do not
batch multiple unrelated recipes in one pass.

## Core Rules

- The catalog is the source of truth for ingredients: every `@id` in the
  recipe must match a catalog id with a gram-reachable unit. Never invent
  an id inline — author the entry first, then reference it.
- Cookware is `data/equipment.yaml` ids as `#tokens` in the body only —
  there is no frontmatter equipment list to keep in sync.
- Guess cooking judgment (times, temps, yield, storage) and say so on the
  read-back; the user corrects like any other guess. Never guess catalog
  facts — those go through the ingredient skill.
- Everything the user posted during brainstorming — pasted specs, macro
  tables, product names, costs — is inspiration, never a verified fact.
  Check and verify each of it through the normal flow (label photo,
  USDA cross-check, sanity bands) before it lands anywhere. Never stage
  user-pasted numbers as `panel`, never skip verification because the
  spec "looks complete".

## Workflow

### 1. Shape the idea

Take the user's starting point — a rough idea, a pasted draft, a photo of
a dish — and reason it into a cookable recipe: cuisine logic, technique
order, balanced macros for the category, realistic batch size. The user is
not a confident cook, so the agent carries the cooking judgment: always
look up similar recipes online (use the browser) and ground technique,
order, times, temps, and ratios in what working recipes do — never wing
it from priors alone. Agree the shape with the user before touching
files: title, category (`modular_protein`, `modular_carb`,
`modular_cooked_veg`, `fresh_salad_veg`, `breakfast`), servings, and the
ingredient list with quantities in concrete units. Paste the agreed list
as an FYI — no formal sign-off needed — with 2–3 similar recipes cited
(URL + what was borrowed: technique, ratios, times/temps). No citations,
no draft: the lookup is the proof the research happened. Every
quantity's unit must already be gram-reachable on its catalog entry, or
be reachable via an edge the agent judges worth authoring (see §2).

### 2. Match ingredients, report, fill gaps

Extract the recipe's ingredient list and match each against the catalog
(`grep -rn "id: <slug>" data/ingredients/`). Then paste a report listing
every recipe ingredient with its status — `existing` (catalog id + unit
available) or `to be added` (new entry, or new unit edge on an existing
entry):

- `@basmati-rice{0.33%cup}` — existing (`cup -> g` on the entry)
- `@miso-paste{2%tbsp}` — to be added (no catalog entry)
- `@chicken-breast{1%fillet}` — to be added (`fillet -> g` edge missing)

Reason about each missing unit edge before authoring it: if the unit is a
sane kitchen measure the entry should support, add the edge to the
ingredient (measured with proper equipment — scale, cups, spoons — never
eyeballed or estimated; anything can be weighed, but volume is usually
more convenient at cook time, so use discretion per ingredient). If it is
exotic or
one-off — a countable nobody cooks with, a package fraction — rewrite the
recipe quantity in a common unit the entry already supports instead. The
test is whether recipes would ever name the unit again; a unit that only
exists in this recipe is not a unit.

Author each `to be added` item by invoking the meal-ingredient skill, one
entry at a time, running its full flow every time: label photo (request
it — never stage user-pasted numbers as `panel`, never render a card
without a real photo), transcription, stage, review card, validate, land
in the aisle file. No printf-and-placeholder shortcuts: the entry is done
only when it validates in its aisle file in the current tree. Return here
after each entry validates.

### 3. Draft the recipe

Write `recipes/<category>/<slug>.cook`: YAML frontmatter (`id` matching
the file stem, `title`, `category`, `yield`, `storage`) plus a Cooklang
body with `@ingredient{quantity%unit}` amounts, `#cookware` tokens, and
`~timer{name%amount%unit}` timers. See an existing `.cook` file for the
shape — never re-specify it here. `fridge_days` must be `<=` the minimum
ingredient shelf life (see the sanity-checks reference of the
meal-ingredient skill).

### 4. Validate, regenerate cards, show

Validate by preparing the recipe against the real catalog (raises on
unknown ingredient, unregistered unit, unknown cookware):

```sh
python -c "from pathlib import Path; import renderer; from meal_prep.library import MealPrepLibrary; lib = MealPrepLibrary.load(data_dir=Path('data'), recipes_dir=Path('recipes')); from meal_prep.services.recipes import prepare_recipe; prepare_recipe(lib.recipes['<slug>'], lib.catalog, lib.equipment); print('ok')"
```

Fix `ValueError`s by correcting the draft, never the service. Then run
the repo gate per `AGENTS.md`, regenerate all cards (force-cleans stale
ones), and open the new card with `show_preview`:

```sh
python -c "from pathlib import Path; import renderer; from meal_prep.library import MealPrepLibrary; lib = MealPrepLibrary.load(data_dir=Path('data'), recipes_dir=Path('recipes')); renderer.render_all_recipe_cards(lib, Path('recipe_cards'))"
```

Present the card with a read-back: per-serving macros, cost, yield, and
which cooking judgments were guesses. Iterate on feedback, or commit when
done — never push to `master`, never merge.
