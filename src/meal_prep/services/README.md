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
  when it is added; remove, move, reorder and relink never recompute them.
- `sessions.py` — prep session items: frozen once, when added (numbers and
  one batch's ingredient lines); `prepare_session` builds the model.
- `prep.py` — prep-session rules and editing modes (`docs/prep-sessions.md`):
  every edit works on the whole diary (links span weeks) and returns the
  documents to write; refusals raise `RuleError` with a user-facing message.
- `heuristics.py` — warn-only opinions, never gating.

## Chesterton's Fences

- An empty `unit` means `count` (the reserved node), not "absent".
- `prep.py` rules are checked by the server on every edit, not by the week
  DTO: a link points at a session in another file, often another week.

## Test

```sh
python -m pytest tests/meal_prep/services -q
```
