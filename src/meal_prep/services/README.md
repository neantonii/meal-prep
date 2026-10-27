# Services

Business logic layer — collaboration is allowed.

## Role & Imports

Enrich DTOs into frozen models. Allowed imports: `dtos`, `models`, `engines`,
`enums`, stdlib. Services own all cross-validation; adapters never do.

## Business Invariants

- All math is raw and unrounded.

- `ingredients.py` — catalog enrichment (synonyms, graph, macros).
- `recipes.py` — recipe enrichment (gram merge, cookware, aggregates).
- `meals.py` — recipe-id resolution into frozen values.
- `logs.py` — diary weeks into `LogWeek`, from their frozen entries only.
- `diary.py` — single-entry diary editing: an entry's numbers are frozen once,
  when it is added; remove, move and reorder never recompute them.
- `heuristics.py` — warn-only opinions, never gating.

## Chesterton's Fences

- An empty `unit` means `count` (the reserved node), not "absent".

## Test

```sh
python -m pytest tests/meal_prep/services -q
```
