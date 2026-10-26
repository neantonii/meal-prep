# Spike: how meals are composed

Status: open question, nothing decided. No code changes come with this note.

## Question

A meal is eaten in two ways:

- **Fixed bundle**: always the same recipes together. Example: the Mon/Wed/Fri
  breakfast (overnight oats + boiled eggs + flat white).
- **Pairing**: one recipe per role, combined freely within rules. Example:
  lunch = 1 protein + 1 carb + 1 cooked veg; rice-stick noodles only with
  minced meat.

How should the domain model represent these, if at all?

## What exists today

- **Roles exist only as recipe folders.** `recipes/<category>/` gives each
  recipe one category (`modular_protein`, `modular_carb`,
  `modular_cooked_veg`, `fresh_salad_veg`, `breakfast`, `snacks`).
- **Bundles are coded but unused.** `MealDTO` / `Meal`, the `meals/*.yaml`
  adapter, `prepare_meal()` and `Library.meals` all exist and are tested, but no
  `meals/` folder is authored and no caller passes `meals_dir` to
  `load_library()` (not the server, not `scripts/render_week.py`).
- **Pairing rules exist only as prose.** L1, D1, B1, B2 and P1 in
  `src/meal_prep/planner/requirements.md`. Nothing in code reads them.
- **The diary stores recipes per mealtime.** `LogDay` holds
  `breakfast/lunch/dinner/snacks` as recipe lists. The UI picks recipes one
  by one. A "meal" in the diary is whatever list sits in a mealtime.
- **The planner PoC ignores both.** It fills each slot with a single recipe
  (breakfast from `breakfast`, lunch/dinner from any recipe).

## Options

| | Model | For | Against |
|---|---|---|---|
| A | **Bundles only.** Every allowed combination is a meal file. | One concept, already built. Explicit. | Combinations explode (6 proteins × 6 carbs × 3 veg = 108 lunches). Rules like P1 enforced by hand. |
| B | **Templates only.** A meal is a set of role slots plus pairing rules; a fixed breakfast is a template with one choice per slot. | One concept. Rules become data. | Awkward for fixed bundles. Needs a rules format. |
| C | **Both.** Keep `Meal` bundles; add a template (role slots + rules). | Matches how meals are actually eaten. | Two concepts to maintain. |
| D | **Status quo.** Rules stay prose; diary stays free-form. | Zero cost. | Neither the UI nor the planner can use the rules. Bundle code stays dead. |

## Open questions

1. **Diary: unit or expansion?** When a bundle is logged, does the diary store
   the bundle id or the recipes it expands to? Storing recipes keeps the diary
   as "what was eaten" (and fits frozen history, #107); the bundle is then
   only a shortcut in the UI.
2. **Are roles one per recipe?** Some recipes could fill two roles (sweet corn
   and peas as carb or as veg). Folder-as-category allows only one.
3. **Rule shape.** Allow-lists ("noodles pair with minced meat") or deny-lists
   ("noodles never with whole cuts")? P1 is written both ways today.
4. **Mealtime ↔ template.** Is lunch always L1 and dinner always D1, or can
   any template fill any mealtime?
5. **Snacks.** Bundle, template, or free choice?
6. **Dead code.** If the answer is B or D, should the unused bundle code be
   removed?

## Smallest useful step, whatever the answer

Bundles as a logging shortcut: author `meals/`, pass `meals_dir` in the server,
and let the UI insert a bundle's recipes into a mealtime. It touches no
diary format and no planner code, and it either proves bundles useful or
shows they are not.
