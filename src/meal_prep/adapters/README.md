# Adapters

Data access — the only code that reads files / parses external formats.

## Role & Imports

Translate on-disk formats (YAML, Cooklang) into DTOs. Allowed imports: `dtos`
and any serialization-related modules (`yaml`, stdlib, etc.).

## Business Invariants

- Deserialization + shape validation only; no cross-validation against the
  catalog/registries.

## Chesterton's Fences

- An empty Cooklang unit is preserved as `""` on the DTO (the service interprets
  it as `count`).
- Recipe `id` must equal filename stem; `category` must equal parent dir name.

## Test

```sh
python -m pytest tests/meal_prep/adapters -q
```
