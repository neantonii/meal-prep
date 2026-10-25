# Models

Enriched, frozen, fully-resolved value objects.

## Role & Imports

Value objects constructed by `services`, never from files. Forbidden imports:
`dtos`, `services`, `adapters`, `renderer`.

## Business Invariants

- Immutable and self-sufficient: a model carries everything it needs
  (conversion graph, synonyms, macros); consumers never resolve collaborators.
- All amounts are raw floats, unrounded — rounding is the renderer's job.
- `Library` (built only by `meal_prep.library.load_library`) is the one
  value consumers start from: enriched ingredients, recipes and meals.

## Chesterton's Fences

## Test

```sh
python -m pytest tests/meal_prep/models -q
```
