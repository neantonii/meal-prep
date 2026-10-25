# Meal Prep — Agent Memory

## Tooling

- **Setup (fresh container)**: `uv sync --locked` (installs the project
  editable plus the `dev` group into `.venv` exactly as `uv.lock` pins it).
  Install uv with `pip install uv` if missing. UI: `cd ui && npm ci`.
- **Python**: 3.13, `src`-layout. Run tools through `uv run` (or activate
  `.venv`); commands below use `uv run`.
- **Lint/format**: [ruff](https://docs.astral.sh/ruff/), config in
  `pyproject.toml`. Run via `uv run ruff ...`.
- **Types**: [mypy](https://mypy.readthedocs.io/) in `strict` mode over `src/`
  only (`tests/` excluded). Config in `pyproject.toml`. Run via
  `uv run mypy` (reads `files = "src"` from config, no path arg needed).
- **Tests**: `uv run pytest -q`.
- **Render a week**: `uv run python scripts/render_week.py plans/2026-W43.yaml`
  (plan → `weekly_plan/log-2026-W43.html`; regenerates cards, relativizes
  links). Diary needs `-o weekly_plan/diary-2026-W43.html`. Never hand-roll
  the load/prepare/render chain inline — the script is the entry point.
- **GitHub CLI**: `gh` is available but needs auth — export `GH_TOKEN="$GITHUB_TOKEN"`
  first (e.g. `export GH_TOKEN="$GITHUB_TOKEN" && gh issue list`). The `GITHUB_TOKEN`
  env var alone is not picked up by `gh`.

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
- Agents never merge: no `gh pr merge`, no merging `master` into a branch
  (rebase only if asked), no pushing to `master`. Merging is the user's
  decision after their own review.
- Agents never modify anything under `.github/` (workflows, the dependency
  policy script, Dependabot config) unless the user explicitly asks for that
  change. GitHub does not enforce this: agents act as the user (see #88).
- Post-merge cleanup: after the user confirms a PR is merged, run
  `git prune-stale` (fetches with prune, deletes local branches whose
  upstream is `[gone]`; `master`/`main` exempt, `git branch -d` refuses
  unmerged work). Then `git checkout master && git pull`.
- `git prune-stale` is a repo-local alias (lives in `.git/config`, not
  cloned). Reinstall on a fresh checkout with:
  `git config alias.prune-stale '!git fetch --prune && git for-each-ref
  --format="%(refname:short) %(upstream:track)" refs/heads | while read -r
  name track; do case "$name" in master|main) continue;; esac; if
  [ "$track" = "[gone]" ]; then git branch -d "$name"; fi; done'`

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
`uv run mypy` must all report clean. Commit only when green.

## Dependencies

- Exact pins only: `==` for every requirement in `pyproject.toml` (build
  backend and dev group included), exact versions in `ui/package.json`.
  Transitive versions live in `uv.lock` / `ui/package-lock.json`; commit lock
  changes together with the manifest change. (Convention; checked in review.)
- Packages come from PyPI / the npm registry only (no git or URL sources).
- Every package version a PR adds to a lock file must be at least 30 days old
  and have no known vulnerability. Never pick "latest"; when adding or
  bumping, choose the newest version that is at least 30 days old
  (`uv lock --exclude-newer <date 30 days ago>` helps).
- Security fixes come through Dependabot, whose PRs skip these checks. Do not
  bump a package to a fresher release by hand to fix an advisory.
- Dependabot opens version updates after a cooldown (30 days patch/minor,
  90 days major); security updates arrive immediately. Packages that become
  vulnerable later surface as Dependabot alerts.

Enforced on every non-Dependabot PR by `.github/workflows/dependency-policy.yml`
(runs `master`'s copy): `actions/dependency-review-action` for vulnerabilities
and `.github/scripts/release_age.py` for release age, both on the
dependency-graph diff between the PR's base and head.

## Ruff config policy

The `select` list is intentionally minimal (currently `E`, `W`, `F`, `I`,
`UP`, `B`, `C4`, `SIM`, `TID252`, `RUF`).
All candidate rules from the original rollout are now enabled. Do not add new
rules silently — talk it through with the user first.
