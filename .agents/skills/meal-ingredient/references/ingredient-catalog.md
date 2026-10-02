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

## Worked Examples

### Simple (no custom units)

Butter uses only standard units; `package -> g` plus one kitchen measure:

```yaml
- id: unsalted-butter
  name: Unsalted Butter
  step_name: butter
  aisle: dairy
  storage: refrigerated
  shelf_life_days: 90

  reference:
    brand: Compliments
    product: Compliments Butter Unsalted 454 g
    price: 6.69

  macros:
    unit: g
    amount: 100
    calories_kcal: 700.0
    protein_g: 1.0
    fat_g: 80.0
    carbs_g: 0.0
    fiber_g: 0.0
    saturated_fat_g: 50.0
    sugars_g: 0.0
    sodium_mg: 0.0
    potassium_mg: 24.0

  conversions:
    - from: package
      to: g
      factor: 454
    - from: tbsp
      to: g
      factor: 14.2
```

### Custom units (garlic)

Non-standard nouns go in `custom_units`; every canonical needs a `-> g` path:

```yaml
  custom_units:
    clove: [clove, cloves]
    head: [head, heads]

  conversions:
    - from: package
      to: head
      factor: 3
    - from: clove
      to: g
      factor: 3.0
    - from: head
      to: g
      factor: 50.0
```

### Count chain (chicken breast)

Recipes using `@boneless-chicken-breast{4}` (empty unit = `count`) need the
two-hop retail chain `package -> count -> g`:

```yaml
  conversions:
    - from: package
      to: count
      factor: 4
    - from: count
      to: g
      factor: 237.5
```

`package_weight_g` derives as `4 * 237.5 = 950 g`; `price_per_100g` follows.
