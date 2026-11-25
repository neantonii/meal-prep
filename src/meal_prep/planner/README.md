# Planner

Fills the week ahead with meals and the prep sessions that cook them
(`docs/planner.md`). The server reads the diary into planner input and
writes the plan back (`server/planning.py`, `services/prep.py`).

## Role & Imports

Consumes `meal_prep.models.Recipe` and `meal_prep.enums`. Only `solver.py`
may import `ortools`; `plan.py` and `quadratic.py` are solver-free. The
archetypes come from `data/archetypes.yaml` through the `Library`.

## Business Invariants

Existing items only fix variables: a pin is a lower bound on its slot's
dish count, history slots are fixed, a cooked batch is fixed and a planned
one keeps at least its batches. The only hard constraints are the diary's
(a batch's meals never exceed its portions; a portion is eaten on or after
its session's date), so pins can never make the model infeasible. The
objective is a sum of named terms (archetype fit, same-day and next-day
repeats, leftovers); each slot chooses one archetype, and the plan only
adds dishes the chosen archetype takes, never overfilling a role.
Deterministic: one worker, fixed seed.

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
