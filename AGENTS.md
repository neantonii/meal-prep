# Meal Prep — Agent Memory

## Tooling

- **Setup (fresh container)**: `pip install -e . pytest ruff mypy`
- **Python**: `python` (3.13). Package is `src`-layout, installed editable
  (`pip install -e .`); deps declared in `pyproject.toml` (`pydantic`, `pyyaml`).
- **Lint/format**: [ruff](https://docs.astral.sh/ruff/) — installed in the
  environment, config in `pyproject.toml`. Run via `python -m ruff ...` (the
  `ruff` binary may not be on `PATH`).
- **Types**: [mypy](https://mypy.readthedocs.io/) in `strict` mode over `src/`
  only (`renderer.py`, `tests/` excluded — `renderer.py` is
  slated to move into `src/`). Config in `pyproject.toml`. Run via
  `python -m mypy` (reads `files = "src"` from config, no path arg needed).
- **Tests**: `python -m pytest -q`.
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
  `models` (frozen enriched dataclasses, clean public names) → `renderer.py`.
  DTO and model of the same concept are *different forms*; see
  `src/meal_prep/dtos/README.md`.

## Version control

- Never push directly to `master`. All work goes on a feature branch +
  pull request (`git checkout -b <name>`, push, `gh pr create`).
- Before raising a PR, squash local iterations into meaningful chunks —
  one commit per logical change. Only keep genuinely separate commits;
  never one commit per edit.
- Agents never merge: no `gh pr merge`, no merging `master` into a branch
  (rebase only if asked), no pushing to `master`. Merging is the user's
  decision after their own review.
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
change under `src/meal_prep/dtos/`, run `python scripts/refresh_schemas.py`
and commit the diff (`tests/test_schemas.py` fails CI when they drift).

## Required workflow after any code edit

Run, in this order, and fix until clean:

```sh
python scripts/refresh_schemas.py # only needed if dtos/ changed
python -m ruff check . --fix
python -m ruff format .
python -m mypy
python -m pytest -q
```

Then `python -m ruff check .`, `python -m ruff format . --check`, and
`python -m mypy` must all report clean. Commit only when green.

## Ruff config policy

The `select` list is intentionally minimal (currently `E`, `W`, `F`, `I`,
`UP`, `B`, `C4`, `SIM`, `TID252`, `RUF`).
All candidate rules from the original rollout are now enabled. Do not add new
rules silently — talk it through with the user first.
