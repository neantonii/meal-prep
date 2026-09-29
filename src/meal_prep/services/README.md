# Services

Business logic layer — collaboration is allowed.

## Role & Imports

## Business Invariants

- All math is raw and unrounded.

## Chesterton's Fences

- An empty `unit` means `count` (the reserved node), not "absent".

## Test

```sh
python -m pytest tests/meal_prep/services -q
```
