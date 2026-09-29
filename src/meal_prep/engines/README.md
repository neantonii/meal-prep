# Engines

Pure computation kernels — no domain imports.

## Role & Imports

Dependency-free logic. Allowed imports: stdlib only. Importing anything from
`meal_prep` is forbidden (enforced by `test_engines_package_has_no_domain_imports`).

## Engines

- `conversion_graph.py` — immutable unit-conversion graph with transitive closure.
- `cooklang.py` — Cooklang recipe text parser.

## Test

```sh
python -m pytest tests/meal_prep/engines -q
```
