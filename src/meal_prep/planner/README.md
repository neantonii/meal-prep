# Planner

Fills the week ahead with meals and the prep sessions that cook them
(`docs/planner.md`). The server reads the diary into planner input and
writes the plan back (`server/planning.py`, `services/prep.py`).

## Role & Imports

Consumes `meal_prep.models.Recipe` and `meal_prep.enums`. Only `solver.py`
may import `ortools`; `plan.py`, `templates.py` and `quadratic.py` are
solver-free.

## Business Invariants

Every slot holds exactly one option of its mealtime's template (each role
filled by one recipe) plus optional extras, nothing else; a recipe is eaten
at most once a day, counting meals already there. Batches per session and
recipe: `uses <= batches * servings`, whole servings only. Points:
leftover portions (not for sessions the horizon cuts off) and next-day
repeats (only when at least one side is planned). Deterministic: one
worker, fixed seed.

Convex quadratic terms (`ConvexQuadratic`, `c·x² + b·x + d`, `c > 0`) on an
integer expression `x` in `[lo, hi]` (`_add_quadratic`): `lo <= x <= hi` is
enforced, `t >= x²` by at most `max_cuts` (default 100) secant cuts, and
`c·t + b·x + d` is returned for the objective. Cuts are exact at
breakpoints: every integer near the vertex, geometrically sparser away from
it (relative overestimate at most `(rho-1)²/(4rho)`).

## Test

```sh
python -m pytest tests/meal_prep/planner -q
```
