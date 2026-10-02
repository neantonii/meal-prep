# Ingredient Catalog Reference

Conventions for one `data/ingredients/<aisle>.yaml` list entry. Authored form
is `IngredientDTO`; enrichment (`prepare_ingredient`) derives the frozen
`Ingredient`. Keep the two forms distinct.

## Field Schema (committed, never hand-edit)

Read `schemas/ingredient.schema.json` directly. It is generated from
`meal_prep.dtos.ingredient.IngredientDTO` and carries every field, type,
constraint, and `Field(description=...)`. `extra="forbid"` on every model:
unknown keys fail shape validation. If the file looks stale, run
`python scripts/refresh_schemas.py` and commit the diff
(`tests/test_schemas.py` guards freshness in CI).

## Template vs DTO

- The DTO (`src/meal_prep/dtos/ingredient.py`, frozen as
  `schemas/ingredient.schema.json`) is the **contract**: every field, type,
  bound (`gt`, `ge`, `min_length`), default, and validator
  (`normalize_slug` kebab-case, `clean_token` case-fold/trim, duplicate-alias
  and self-conversion rejection, `extra="forbid"`). Machine-checked; on any
  conflict with skill text, the schema wins.
- The template (`assets/ingredient-template.yaml`) is a **starting point**:
  one entry skeleton with `TODO(user)` markers and inline hints. It simplifies
  — `from:`/`to:` as authored (the DTO aliases them to `from_unit`/`to_unit`),
  optional nutrients commented out, conversion scaffolding pre-shaped, aisle
  options hinted (truth is `data/aisles.yaml` plus the file-stem check).
- Copy the template into the aisle file in id-sorted position, replace every
  `TODO(user)` with a user-supplied fact, never invent. Delete the hint
  comments before saving.

## File Placement

- One file per aisle: `data/ingredients/<aisle>.yaml` (top-level YAML list).
- `aisle` field must equal the file stem (`load_ingredients_file` enforces).
- `id` globally unique across all aisle files (`load_all_ingredients` enforces).
- Append in id-sorted position to match file convention.

## Naming

- `name` is for tables and lists; `step_name` is for flowing instruction text
  and renderer badges. Copy the casing/style of sibling rows; casing is
  convention observed in data, not a validation rule.
- `id` mirrors the retail item, not the recipe usage: `boneless-chicken-breast`,
  not `chicken`.
- Custom-unit canonicals are slugs (`clove`); aliases cover plurals and
  variants (`[clove, cloves]`).

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
