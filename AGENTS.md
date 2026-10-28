# Meal Prep — Agent Memory

## Tooling

- **Setup (fresh container)**: `uv sync --locked` (installs the project
  editable plus the `dev` and `planner` groups into `.venv` exactly as
  `uv.lock` pins it). The `planner` group (OR-Tools) is kept out of
  `[project]` so the server image doesn't ship it; add planner-only
  dependencies with `uv add --group planner`.
  Install uv with `pip install uv` if missing. UI: `cd ui && npm ci` on the
  Node major in the Dockerfile's `ui` stage.
- **CI = the Dockerfile.** Python, Node and uv versions live only in the
  `Dockerfile` (digest-pinned `FROM` lines, updated by Dependabot); workflows
  install no toolchains (`tests/test_deploy.py`). CI's checks are
  `docker build --target test .` (ruff, mypy, pytest) and
  `docker build --target ui .` (UI lint, typecheck, build); run them locally
  to reproduce CI exactly. Local `uv run ...` is for fast iteration.
- **Python**: 3.13, `src`-layout. Run tools through `uv run` (or activate
  `.venv`); commands below use `uv run`.
- **Lint/format**: [ruff](https://docs.astral.sh/ruff/), config in
  `pyproject.toml`. Run via `uv run ruff ...`.
- **Types**: [mypy](https://mypy.readthedocs.io/) in `strict` mode over `src/`
  only (`tests/` excluded). Config in `pyproject.toml`. Run via
  `uv run mypy` (reads `files = "src"` from config, no path arg needed).
- **Tests**: `uv run pytest -q`.
- **Render a diary week**: `uv run python scripts/render_week.py diary/2026-W43.yaml`
  (→ `weekly_plan/diary-2026-W43.html`; regenerates cards, relativizes
  links). Never hand-roll the load/prepare/render chain inline — the script
  is the entry point.
- **GitHub CLI**: `gh` is available but needs auth — export `GH_TOKEN="$GITHUB_TOKEN"`
  first (e.g. `export GH_TOKEN="$GITHUB_TOKEN" && gh issue list`). The `GITHUB_TOKEN`
  env var alone is not picked up by `gh`. Agents act on GitHub as
  `neantonii-bot` (a write collaborator), not as the owner.

## Code style

- `from __future__ import annotations` in every module (postponed evaluation).
- Type hints use modern syntax (`X | Y`, builtin generics `list[...]`,
  `dict[...]`); target Python 3.12.
- Line length 88; quotes `"` (double); import order via isort (first-party =
  `meal_prep`).
- Layer convention: `dtos` (Pydantic, authored/raw, `...DTO` suffix) →
  `models` (frozen enriched dataclasses, clean public names) → `renderer`.
  DTO and model of the same concept are *different forms*; see
  `src/meal_prep/dtos/README.md`.
- Two tiers: the loading machinery (`adapters`, `dtos`, `services`) feeds
  `load_library()`, which returns a frozen `Library` of enriched models.
  Consumers (`renderer`, `ingredient_cards`, `logbook`, `planner`) take
  models or the `Library` only and never import the machinery
  (`tests/test_consumer_imports.py`). Entry points on an I/O boundary
  (`server`, `scripts/`) may use both.

## Version control

- Never push directly to `master`. All work goes on a feature branch +
  pull request (`git checkout -b <name>`, push, `gh pr create`).
- `plans/` and `diary/` are gitignored personal data — never commit them,
  never force-add them for PR review (TEMP plan commits leak personal data
  into the PR history even if dropped before merge). Demo/render locally only.
- Never `git clean -fdx` blindly — it deletes `plans/`, `diary/`, and `.agent_tmp/`.
  Prefer `git clean -fdx -e plans -e diary -e .agent_tmp` or clean specific paths.
- Before raising a PR, squash local iterations into meaningful chunks —
  one commit per logical change. Only keep genuinely separate commits;
  never one commit per edit.
- Merging: the owner's approval is the gate; after it, the agent may merge
  its own PR when it judges the time right (e.g. hold it until a PR it
  depends on lands).
  - Only a PR the agent opened, only once the owner has approved its
    current head, with CI green and no open review threads. Any push after
    the approval (fix, rebase) needs a fresh approval before merging.
  - Rebase merge (squash is refused on `master`), pinned to the approved
    head: `gh pr merge <n> --rebase --match-head-commit <sha>`.
  - Order: when approved PRs depend on each other or touch the same files
    (two `VERSION` bumps included), merge one at a time in dependency
    order. After each merge, check that the next PR is still mergeable and
    green on the new `master`; if it needs a rebase, rebase, push and wait
    for re-approval.
  - A merge deploys within the hour (README, "Every merge to `master`
    reaches the host"). A PR that needs a manual step on the host is
    merged only when the owner says so.
  - Never push to `master`; never merge `master` into a branch (rebase
    instead); never merge PRs the agent didn't open (Dependabot's, the
    owner's) unless asked.
- Agents never modify anything under `.github/` (workflows, the dependency
  policy script, Dependabot config) unless the user explicitly asks for that
  change. GitHub does not enforce this: the agent account (`neantonii-bot`)
  can push workflow changes to any branch (see #138).

## Product version

`MAJOR.MINOR.PATCH`, shown in the UI header and served at `/api/version`.
`VERSION` holds `MAJOR.MINOR`; PATCH is the image workflow's run number
(`github.run_number`), added by CI. GitHub never reuses a run number, so
versions never repeat, whatever anyone forgets; PR runs use numbers too, so
published versions have gaps.

- MAJOR: the owner only. Agents never change it.
- MINOR: agents may bump it in a PR that adds a user-visible feature; say so
  in the PR description. PATCH does not reset.
- PATCH: never written anywhere.
- Renaming or recreating `.github/workflows/image.yml` restarts the run
  number at 1: bump MINOR in the same change so versions stay unique.

## Diary data migrations

A change that alters how diary or session files are stored (a new field
that existing files should have, a rename, a move) ships a migration in
`src/meal_prep/migrations/` (see its `__init__` docstring): the next number,
raw YAML edits (never today's DTOs), idempotent, with a test from old-format
files. The server applies it on start-up after a backup, so no manual host
step is needed. Never edit or renumber a released migration.

## Committed schemas

`schemas/*.schema.json` are generated from the DTOs, not authored. After any
change under `src/meal_prep/dtos/`, run `uv run python scripts/refresh_schemas.py`
and commit the diff (`tests/test_schemas.py` fails CI when they drift).

## Required workflow after any code edit

Run, in this order, and fix until clean:

```sh
uv run python scripts/refresh_schemas.py # only needed if dtos/ changed
uv run ruff check . --fix
uv run ruff format .
uv run mypy
uv run pytest -q
```

Then `uv run ruff check .`, `uv run ruff format . --check`, and
`uv run mypy` must all report clean. Before pushing, `docker build --target
test .` is the exact CI check. Commit only when green.

## Dependencies

Every PR not opened by Dependabot fails CI (`dependency-policy`, a required
check) if it adds a package version that is **younger than 30 days** or has a
**known vulnerability**. Only the PR's own lock-file additions are checked.
Get it right up front instead of iterating against CI:

**Choosing**
- Prefer the standard library or a package already in use. Ask the user
  before adding a new dependency; when one is needed, pick a mature, widely
  used, maintained package.
- Exact pins in `pyproject.toml` (`==`) and `ui/package.json`; PyPI / npm
  registry only (no git or URL sources). Commit manifest and lock together.

**Adding or bumping** (the cutoff also applies to transitive packages)
```sh
# Python: resolve with a cutoff, then re-lock without it (versions stay; the
# second run only removes the cutoff that the first one records in uv.lock)
uv add "<pkg>==<version>" --exclude-newer "$(date -u -d '30 days ago' +%F)"
uv lock
# UI (Node/npm version from the Dockerfile `ui` stage)
cd ui && npm install <pkg>@<version> --min-release-age=30
```
Pick the newest version that is at least 30 days old, never "latest".

**Self-check before opening the PR** (after `git push`; same data CI uses)
```sh
export GITHUB_REPOSITORY=neantonii/meal-prep \
  BASE_SHA=$(git merge-base HEAD origin/master) HEAD_SHA=$(git rev-parse HEAD)
python .github/scripts/release_age.py   # the exact release-age check CI runs
curl -s "https://api.github.com/repos/$GITHUB_REPOSITORY/dependency-graph/compare/$BASE_SHA...$HEAD_SHA" \
  | python -c "import json,sys; [print(c['name'], c['version'], [v['advisory_ghsa_id'] for v in c['vulnerabilities']]) for c in json.load(sys.stdin) if c['vulnerabilities']]"
```
The second command prints nothing when no added version is vulnerable.

**When a check fails, do not fight it**
- Too fresh: pick an older version. Vulnerable: pick a version without the
  advisory that is still 30+ days old.
- If no version is both old enough and clean (typically: the only fix is
  newer than 30 days), stop and tell the user. Security fixes come through
  Dependabot, whose PRs skip these checks; never hand-bump to a fresh fix.
- Never edit the check, its workflow, or Dependabot config to get green
  (see the `.github/` rule above).

Background: Dependabot proposes version updates after a cooldown (30 days
patch/minor, 90 days major) and opens security updates immediately; packages
that become vulnerable later surface as Dependabot alerts. CI runs
`actions/dependency-review-action` and `.github/scripts/release_age.py` from
`master` on the dependency-graph diff between the PR's base and head.

## Ruff config policy

The `select` list is intentionally minimal (currently `E`, `W`, `F`, `I`,
`UP`, `B`, `C4`, `SIM`, `TID252`, `RUF`).
All candidate rules from the original rollout are now enabled. Do not add new
rules silently — talk it through with the user first.
