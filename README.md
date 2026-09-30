# Meal Prep

Recipe batch-prep system: authored `.cook`/YAML data → validated DTOs →
enriched frozen models → rendered HTML cards.

## Layout

- `data/` — authored taxonomies and ingredient catalog (YAML)
- `recipes/` — authored recipes (Cooklang, `<category>/<slug>.cook`)
- `recipe_cards/` — rendered HTML output
- `renderer.py` — HTML card renderer (reads enriched models, emits HTML)
- `src/meal_prep/` — the Python package:
  - `dtos/` — Pydantic schemas for authored data; shape validation only
  - `adapters/` — reads files (YAML/Cooklang), produces DTOs
  - `engines/` — pure dependency-free kernels (conversion graph, Cooklang parser)
  - `models/` — frozen, enriched value objects
  - `services/` — business logic; resolves DTOs → models
  - `enums.py` — shared enum types
  - `library.py` — top-level loader gateway
- `planner/` (under `src/meal_prep/`) — weekly meal planner (7 days × 3 meals, CP-SAT):
  - `solver.py` — owns the OR-Tools import; cheapest one-recipe-per-meal plan
  - `plan.py` — frozen `WeekPlan` value with day/week aggregates
  - `report.py` — standalone HTML report (links each meal to its recipe card)
- `weekly_plan/` — generated plan report (git-ignored)
- `tests/` — pytest suite

## Module documentation

Every package submodule carries its own `README.md` following a fixed,
succinct template (target < 25 lines):

- **Role & Imports** — one sentence on ownership + the *allowed* imports (the
  short positive list; everything else is forbidden).
- **Business Invariants** — unbreakable domain rules not enforced by types
  (state flows, math precision, atomic scopes). Leave the section **empty** if
  nothing is worth mentioning.
- **Chesterton's Fences** — intentional quirks, odd workarounds, or rejected
  patterns that look like bugs but must never be refactored. Leave empty if
  none.
- **Test** — single-line CLI command to test this folder in isolation.

Read each `README.md` for the layer's implicit conventions before editing code
there.
