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

The container uses the host's time zone (`/etc/localtime`, mounted in
`compose.example.yml`) to decide which day is "today", which splits Plan from
Log. Check it with `timedatectl` on the host; a host on UTC turns the day over
hours early in the evening.

If `docker compose pull` is denied, the GHCR package is private (the
default for a new package): make it public under the repo's *Packages* →
*Package settings*, or run `docker login ghcr.io` on the host with a token
that has `read:packages`.

The running version (`MAJOR.MINOR.PATCH · commit`) shows in the UI header
and at `/api/version`; see "Product version" in `AGENTS.md`.

Upgrade: run `docker compose pull && docker compose up -d` again. Host dirs
are untouched. To roll back, set `image:` to a `:sha-<12-char commit>` tag
(the header shows the first 7 characters of that commit) and run
`docker compose up -d`; switch back to `:latest` to resume updates.

Automatic updates: put this `update.sh` next to `compose.yml`. When no new
image exists it changes nothing (no restart); otherwise the app is down for a
few seconds while the container is swapped.

```sh
#!/bin/sh
# Pull the latest image; recreate the container only if it changed.
set -eu
cd "$(dirname "$0")"
docker compose pull --quiet
docker compose up -d
docker image prune -f >/dev/null   # drop the old image it replaced
```

Run it hourly from cron (the user needs Docker access without `sudo`, i.e.
membership in the `docker` group; otherwise use root's crontab). The log
lives next to `compose.yml`, not in `logs/`, which belongs to the container's
user (uid 1000):

```sh
chmod +x update.sh
(crontab -l 2>/dev/null; echo "17 * * * * $PWD/update.sh >> $PWD/update.log 2>&1") | crontab -
```

Every merge to `master` reaches the host within the hour; a change that
needs a manual step says so in its PR.

**Data migrations run by themselves.** When the stored diary format changes,
the release carries a migration (`src/meal_prep/migrations/`). On start-up
the server compares the diary's version (`diary/.migrations.yaml`) with the
migrations it knows; if any are newer, it first copies the diary to
`diary/.backups/<UTC time>-before-<n>/`, then applies them in order and
checks that every file still loads. If one fails, the server does not start
(the log names the error and the backup) and serves nothing half-migrated.
A new, empty diary is just marked current.

Check what ran (from the host dir, e.g. `/srv/meal-prep`):

```sh
docker compose logs diary | grep -i migrat   # "backed up to …", "migration 1 …"
cat diary/.migrations.yaml                   # version and history
ls diary/.backups                            # one folder per upgrade that migrated
```

Rolling back past a migration (back to an image older than it): restore the
backup taken before it, then pin the older image. Images from this release
on refuse to start on data migrated beyond what they know, rather than
misreading it.

```sh
cd /srv/meal-prep
docker compose down
OLD=rollback/diary-$(date +%Y%m%dT%H%M%S)
mkdir -p rollback && mv diary "$OLD"                 # keep the current diary
BACKUP=$(ls -d "$OLD"/.backups/*-before-* | tail -1) # newest; pick another if needed
mkdir diary && cp -a "$BACKUP"/. diary/              # the files as they were
sudo chown -R 1000:1000 diary                        # the container's user
# set `image:` in compose.yml to ghcr.io/neantonii/meal-prep:sha-<older commit>
docker compose up -d
```

The current diary, with all its backups, is kept under `rollback/` rather
than deleted. A backup never contains `.migrations.yaml` (dot-files are not
copied), so the restored diary reads as "before any migration". That is
right while there is one migration; with more, write the backup's number
minus one into it (`echo "version: 2" > diary/.migrations.yaml` for
`before-0003`). Backups are never deleted automatically; prune old ones by
hand.

The server boots with an empty diary dir and creates a week file when the
first entry of that week is logged.

Diary entries are frozen (#107): each one stores the recipe's title, cost and
nutrition as they were when it was logged, so past weeks never change when
recipes, ingredients or prices do.

Prep sessions (`docs/prep-sessions.md`) live next to the weeks, one file per
session day (`diary/sessions/2026-11-01.yaml`), created on first use; their
items are frozen the same way. Diary entries link to the session they came
from. Days after today are planned (auto-fill on), today and earlier are
logged, and the header's Admin switch amends history.

The UI is at `http://127.0.0.1:8080` on the host; the port is bound to
loopback because the server has no auth (put a reverse proxy in front before
exposing it). The container has a health check on `/api/health`
(`docker ps` shows `healthy`).

Backup/restore: the diary is plain YAML, one file per week
(`diary/2026-W43.yaml`) plus one per prep session (`diary/sessions/`); back
up the whole directory:

```sh
rsync -a /srv/meal-prep/diary/ /backup/meal-prep/diary/
```

Restore by rsyncing back. The server picks up changed files on the next
request, so no restart is needed.
