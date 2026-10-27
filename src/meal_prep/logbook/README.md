# Logbook

Eaten-week HTML report over resolved logs (no planning, no batches).

## Role & Imports

Consumes `meal_prep.models.log.LogWeek` (+ optionally the current
`meal_prep.models.Recipe` lookup, only for card links). Titles, cost and macros
come from the week's entries: the numbers frozen when each was logged. Allowed imports: `models`, `enums`, stdlib. No `dtos`, `services`,
`adapters`, `ortools`.

## Business Invariants

- One serving per logged entry; duplicates sum twice.
- Slots render in `Mealtime` enum order; absent slots are omitted.
- All amounts raw until render; rounding is the report's job.
- A recipe that no longer exists still renders, by its frozen title, without a
  card link.

## Test

```sh
python -m pytest tests/meal_prep/logbook -q
```
