# Meal Prep — Agent Memory

## Tooling

- **Python**: `python` (3.13). Package is `src`-layout; tests bootstrap via
  `conftest.py` (no install needed — `import meal_prep` resolves from `src/`).
- **Lint/format**: [ruff](https://docs.astral.sh/ruff/) — installed in the
  environment, config in `pyproject.toml`. Run via `python -m ruff ...` (the
  `ruff` binary may not be on `PATH`).
- **Tests**: `python -m pytest -q`.

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
python -m pytest -q
```

Then `python -m ruff check .` and `python -m ruff format . --check` must both
report "All checks passed!". Commit only when green.

## Ruff config policy

The `select` list is intentionally minimal (currently `E`, `W`, `F`, `I`,
`UP`, `B`, `C4`).
Candidate rules (`SIM`, `TID252`, `RUF`) are commented out in
`pyproject.toml` and are being enabled one-by-one after discussing/refactoring
each category. Do not silently re-enable a commented-out rule — talk it through
with the user first.
