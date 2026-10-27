# Meal Prep

Recipe batch-prep system: authored `.cook`/YAML data → validated DTOs →
enriched frozen models → rendered HTML cards.

## Layout

- `data/` — authored taxonomies and ingredient catalog (YAML)
- `recipes/` — authored recipes (Cooklang, `<category>/<slug>.cook`)
- `recipe_cards/` — rendered HTML output
- `src/meal_prep/renderer.py` — HTML card renderer (reads enriched models, emits HTML)
- `src/meal_prep/` — the Python package:
  - `dtos/` — Pydantic schemas for authored data; shape validation only
  - `adapters/` — reads files (YAML/Cooklang), produces DTOs
  - `engines/` — pure dependency-free kernels (conversion graph, Cooklang parser)
  - `models/` — frozen, enriched value objects
  - `services/` — business logic; resolves DTOs → models
  - `enums.py` — shared enum types
  - `library.py` — `load_library()`: loads and enriches everything into one
    frozen `Library` (ingredients, recipes, meals); consumers start here
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

## Diary server (deploy)

The FastAPI server (`src/meal_prep/server/`) and the React week editor (`ui/`)
ship as one container image. CI (`.github/workflows/image.yml`) builds and
smoke-tests it on every PR and publishes it on every push to `master`:

- `ghcr.io/neantonii/meal-prep:latest`
- `ghcr.io/neantonii/meal-prep:sha-<12-char commit>` (pin one to roll back)

Reference data (`data/`, `recipes/`) and the UI bundle are baked into the
image; only writable state lives on the host. Python packages come from
`uv.lock`, UI packages from `ui/package-lock.json`, and base images are pinned
by digest, so the image contains exactly what CI checked.

Host setup (all state in one dir, e.g. `/srv/meal-prep`):

```sh
mkdir -p /srv/meal-prep/diary /srv/meal-prep/logs
sudo chown -R 1000:1000 /srv/meal-prep/diary /srv/meal-prep/logs  # container user
cd /srv/meal-prep
# copy compose.example.yml here as compose.yml
docker compose pull && docker compose up -d
```

If `docker compose pull` is denied, the GHCR package is private (the
default for a new package): make it public under the repo's *Packages* →
*Package settings*, or run `docker login ghcr.io` on the host with a token
that has `read:packages`.

The running version (`MAJOR.MINOR.PATCH · commit`) shows in the UI header
and at `/api/version`; see "Product version" in `AGENTS.md`.

Upgrade: run `docker compose pull && docker compose up -d` again. Host dirs
are untouched. To roll back, set `image:` to a `:sha-…` tag.

The server boots with an empty diary dir and creates a week file when the
first entry of that week is logged.

Diary entries are frozen (#107): each one stores the recipe's title, cost and
nutrition as they were when it was logged, so past weeks never change when
recipes, ingredients or prices do. Diary weeks written before this change list
bare recipe ids; the server refuses them with a message until they are
converted once (each original is kept as `<week>.yaml.bak`; re-running is
harmless):

```sh
docker compose exec diary python scripts/migrate_diary.py \
  --diary-dir /app/diary --data-dir /app/data --recipes-dir /app/recipes
``` The UI is at `http://127.0.0.1:8080` on the host; the port is bound to
loopback because the server has no auth (put a reverse proxy in front before
exposing it). The container has a health check on `/api/health`
(`docker ps` shows `healthy`).

Backup/restore: the diary is plain YAML, one file per week
(`diary/2026-W43.yaml`):

```sh
rsync -a /srv/meal-prep/diary/ /backup/meal-prep/diary/
```

Restore by rsyncing back. The server reads week files on each request, so no
restart is needed.
