# Planner

Cheapest 7-day × 3-meal assignment via CP-SAT.

## Role & Imports

Consumes `meal_prep.models.Recipe`. Only `solver.py`/`constraints.py` may
import `ortools` (`plan.py`/`report.py` stay solver-free).

## Business Invariants

Costs scaled to integer cents; exactly one recipe per meal; breakfasts from
`BREAKFAST`-category recipes only; deterministic seed.

## Constraints

One function per model rule in `constraints.py` (a rule earns its own module
past ~30 lines or its own test file). Candidate filtering (pure Python, e.g.
breakfast category) stays in `solver.py` until a second filter appears.

## Test

```sh
python -m pytest tests/meal_prep/planner -q
```
