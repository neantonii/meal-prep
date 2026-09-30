# Meal Prep — Agent Memory

## Tooling

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

## Required workflow after any code edit

Run, in this order, and fix until clean:

```sh
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
