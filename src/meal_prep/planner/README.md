# Planner

Cheapest 7-day × 3-meal assignment via CP-SAT.

## Role & Imports

Consumes `meal_prep.models.Recipe`. Only `solver.py` may import `ortools`.

## Business Invariants

Costs scaled to integer cents; exactly one recipe per meal; deterministic seed.

## Test

```sh
python -m pytest tests/meal_prep/planner -q
```
