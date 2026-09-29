# DTOs

Pydantic models that define the authored-data schemas and validate shape.

Mirrors the authored files — `data/aisles.yaml`, `data/equipment.yaml`,
`data/units.yaml`, `data/ingredients/*.yaml`, `recipes/**/*.cook` — without
reading them.

## Role & Imports

Declare schemas; validate shape only (no file I/O — adapters read files, then
hand dicts here). Allowed imports: `pydantic`, stdlib, and `meal_prep.enums`
(plus dtos-internal). Nothing else.

## Business Invariants

- `id` fields must be kebab-case slugs (`boneless-chicken-breast`).

## Chesterton's Fences

- `Ingredient.name` starts with a capital letter; `Ingredient.step_name` starts
  lowercase.
- `RecipeIngredientRef.unit` `""` means "count", not "absent".
- `from`/`to`/`yield`/`storage` are YAML keys but Python reserved-ish names, so
  fields are aliased (`from_unit`, `yield_info`, …) with `populate_by_name=True`.
  Both spellings work; do not "fix" the redundancy.

## Test

```sh
python -m pytest tests/meal_prep/dtos -q
```





