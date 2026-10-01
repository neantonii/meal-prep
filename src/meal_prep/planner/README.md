# Planner

Cheapest 7-day × 3-meal assignment via CP-SAT, covered by cooked batches.

## Role & Imports

Consumes `meal_prep.models.Recipe`. Only `solver.py` may import `ortools`.

## Business Invariants

Batch costs scaled to integer cents; exactly one recipe per meal; breakfasts
from `BREAKFAST`-category recipes only; one integer batch variable (0–21)
per recipe with `uses <= batches * servings` (leftovers tolerated, charged
at full batch cost); deterministic seed.

## Test

```sh
python -m pytest tests/meal_prep/planner -q
```
