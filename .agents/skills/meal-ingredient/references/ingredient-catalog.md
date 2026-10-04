# Ingredient Catalog Reference

Net-new authoring conventions for one `data/ingredients/<aisle>.yaml` list
entry. Field definitions live in `schemas/ingredient.schema.json` (generated
from `meal_prep.dtos.ingredient.IngredientDTO` — the contract; on any conflict
with skill text, the schema wins). `name` vs `step_name` semantics live in
`src/meal_prep/dtos/README.md`. Read both there, not here.

## File Placement

- One file per aisle: `data/ingredients/<aisle>.yaml` (top-level YAML list).
- `aisle` field must equal the file stem (`load_ingredients_file` enforces).
- `id` globally unique across all aisle files (`load_all_ingredients` enforces).
- Append in id-sorted position to match file convention.

## Exemplar Entries (read live, never copy here)

Study these in `data/ingredients/` before authoring; they cover the three
shapes you will encounter. Read the files, don't rely on memory — values
change as prices and packs change.

- **Simple, no custom units** — `unsalted-butter` in `dairy.yaml`: standard
  units only, `package -> g` plus one kitchen measure (`tbsp -> g`).
- **Custom units** — `fresh-garlic` in `produce.yaml`: non-standard nouns in
  `custom_units` (`clove`, `head`), each with a `-> g` path; retail edge is
  `package -> head`.
- **Count chain** — `boneless-chicken-breast` in `meat.yaml`: recipes using
  `@boneless-chicken-breast{4}` (empty unit = `count`) need the two-hop
  retail chain `package -> count -> g`; `package_weight_g` and
  `price_per_100g` derive from it.

When in doubt, browse the sibling file for the target aisle first — copy the
casing, layout, and conversion style of neighboring rows.
