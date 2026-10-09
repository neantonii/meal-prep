# Logbook

Eaten-week HTML report over resolved logs (no planning, no batches).

## Role & Imports

Consumes `meal_prep.models.log.LogWeek` (+ `meal_prep.models.Recipe` for card
links). Allowed imports: `models`, `enums`, stdlib. No `dtos`, `services`,
`adapters`, `ortools`.

## Business Invariants

- One serving per logged entry; duplicates sum twice.
- Slots render in `Mealtime` enum order; absent slots are omitted.
- All amounts raw until render; rounding is the report's job.

## Test

```sh
python -m pytest tests/meal_prep/logbook -q
```
