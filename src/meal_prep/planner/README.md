# Planner

Cheapest 7-day × 3-meal assignment via CP-SAT, covered by cooked batches.

## Role & Imports

Consumes `meal_prep.models.Recipe`. Only `solver.py` may import `ortools`;
`quadratic.py` (term spec, breakpoint placement) is solver-free.

## Business Invariants

Batch costs scaled to integer cents; exactly one recipe per meal; breakfasts
from `BREAKFAST`-category recipes only; one integer batch variable (0–7,
one cook session per recipe per day) per recipe with
`uses <= batches * servings` (leftovers tolerated, charged at full batch
cost); deterministic seed.

Convex quadratic terms (`ConvexQuadratic`, `c·x² + b·x + d` in cents,
`c > 0`) on an integer expression `x` in `[lo, hi]`: `lo <= x <= hi` is
enforced, `t >= x²` by at most `max_cuts` (default 100) secant cuts,
`c·t + b·x + d` joins the objective. Cuts are exact at breakpoints: every
integer near the vertex, geometrically sparser away from it (relative
overestimate at most `(rho-1)²/(4rho)`). `plan_week(..., daily_kcal=q)`
applies one to each day's kcal.

## Test

```sh
python -m pytest tests/meal_prep/planner -q
```
