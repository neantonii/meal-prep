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
look up similar recipes online and ground technique, order, times, temps,
and ratios in what working recipes do — never wing it from priors alone.
Research from the sites in `references/recipe-sites.md`; the file says
how to read each one (JSON-LD or page text). Before the first lookup,
check that the environment allows every host the file marks `allowed`
(see the file's "Before researching" step) and ask for any that are
missing. Find candidate pages with web search, fetch 2–3 with curl. A site
not on the list goes through that file's "Adding a site" step first.

Agree the shape with the user before touching files: title, category (`modular_protein`, `modular_carb`,
`modular_cooked_veg`, `fresh_salad_veg`, `one_dish`, `breakfast`, `snacks`),
servings, and the ingredient list with quantities in concrete units. Paste the agreed list
as an FYI — no formal sign-off needed — with 2–3 similar recipes cited
(URL + what was borrowed: technique, ratios, times/temps). No citations,
no draft: the lookup is the proof the research happened. Every
quantity's unit must already be gram-reachable on its catalog entry, or
be reachable via an edge the agent judges worth authoring (see §2).

A `one_dish` recipe is a whole lunch or dinner cooked as one batch (soup,
stew, stuffed vegetables, casserole) and replaces a modular plate (protein
+ carb + veg). Its portion must land in the plate band: roughly
550–750 kcal, at least 45 g protein, 50–85 g carbs, at most 30 g fat.
Short of it (soups usually are), raise the meat or add a serving-time
extra inside the recipe itself (a sourdough slice or croutons, a spoon of
yogurt or cream cheese), so the card's per-portion macros are the whole
meal.

### 2. Match ingredients, report, fill gaps

Extract the recipe's ingredient list and match each against the catalog
(`grep -rn "id: <slug>" data/ingredients/`). Then paste a report listing
every recipe ingredient with its status — `existing` (catalog id + unit
available) or `to be added` (new entry, or new unit edge on an existing
entry):

- `@basmati-rice{1/3%cup}` — existing (`cup -> g` on the entry)
- `@miso-paste{2%tbsp}` — to be added (no catalog entry)
- `@chicken-breast{1%fillet}` — to be added (`fillet -> g` edge missing)

Reason about each missing unit edge before authoring it: if the unit is a
sane kitchen measure the entry should support, add the edge to the
ingredient (measured with proper equipment — scale, cups, spoons — never
eyeballed or estimated; anything can be weighed, but volume is usually
more convenient at cook time, so use discretion per ingredient — rice and
oats scoop cleanly into a cup, long pasta and rice noodles do not fit one
and stay in grams). If it is
exotic or
one-off — a countable nobody cooks with — rewrite the
recipe quantity in a common unit the entry already supports instead. The
test is whether anyone would measure with the unit again; a unit that only
exists in this recipe is not a unit. When the recipe names a countable
("3 stalks", "1/2 bunch"), reason about the cook measuring — not the panel
wording — before asking for a new edge (see meal-ingredient §2).

Whole-package quantities never need a new unit or a gram expansion: when
the recipe consumes a whole package or half of one, write
`@id{1%package}` / `@id{1/2%package}` directly — `package` is
gram-reachable on every entry, so no edge is needed. Other fractions
(thirds, quarters) are awkward to portion and do not divide most packs
cleanly — scale the recipe to a whole or half package instead, or weigh
out grams. Never expand a whole
package into grams (`@coleslaw-mix{397%g}`): the gram figure is an awkward
retail artifact, and the checklist renders `1 package` while the step text
shows the ingredient name either way (amounts are omitted from step
badges — see the custom-unit caveat in meal-ingredient §3).

Author each `to be added` item by invoking the meal-ingredient skill, one
entry at a time, running its full flow every time: label photo (request
it — never stage user-pasted numbers as `panel`, never fake a photo;
with none, the card renders without one), transcription, stage, review card, validate, land
in the aisle file. No printf-and-placeholder shortcuts: the entry is done
only when it validates in its aisle file in the current tree. Return here
after each entry validates.

### 3. Draft the recipe

Write `recipes/<category>/<slug>.cook`: YAML frontmatter (`id` matching
the file stem, `title`, `category`, `yield`, `storage`) plus a Cooklang
body with `@ingredient{quantity%unit}` amounts, `#cookware` tokens, and
`~timer{name%amount%unit}` timers — the name is mandatory
(quantities accept fractions and mixed numbers: `@syrup{1/2%tbsp}`,
`@flour{1 1/2%cup}`)
(`~chill{8%hour}`, never bare `~8%hour`: braceless timers fail validation).
See an existing `.cook` file for the
shape — never re-specify it here. `fridge_days` is how long the *cooked*
batch keeps in the fridge, not how long its raw ingredients keep before
cooking (`shelf_life_days`, which matters for shopping and prep timing).
Use food-safety guidance for cooked leftovers: 3–4 days for cooked meat,
poultry and mixed dishes, less for fish and seafood (2–3) and anything
with raw dressing or fresh dairy toppings stored mixed in.

Write body prose for a human cook, not a lab notebook: plain-text liquid
amounts use the friendliest unit (`1 liter`, not `1000 ml`; `1 tbsp`,
not `15 ml`; `1/2 cup`, not `120 ml`). `@ingredient{}` quantities stay
in catalog units (they must validate); prose amounts carry no such
constraint, so pick whatever reads naturally. Never copy an awkward
phrasing from a sibling recipe — match its technique, not its units.

### 4. Validate, regenerate cards, show

Validate and regenerate every card with the one script; name the recipe
to get its per-portion numbers for the read-back and a check of its card
for timer residue (a stray `%` from a malformed `~timer`):

```sh
uv run python scripts/render_cards.py <slug>
```

Loading the library is the validation (unknown ingredient, unregistered
unit, unknown cookware raise before anything is written). Fix `ValueError`s
by correcting the draft, never the service. Then run the repo gate per
`AGENTS.md`.

Show the card. With a preview pane, open
`recipe_cards/<category>/<slug>.html` there. Without one (cloud sessions;
the phone viewer shows HTML as source), screenshot it and send the PNGs,
one per screen:

```sh
node .agents/skills/meal-ingredient/scripts/screenshot.js recipe_cards/<category>/<slug>.html .agent_tmp/card-<slug>
```

Present the card with a read-back: per-serving macros, cost, yield, and
which cooking judgments were guesses. Iterate on feedback, or commit when
done — never push to `master`; merge only per `AGENTS.md` (after the
owner approves the PR).
