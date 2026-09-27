# Design

This document captures the intended architecture. It describes *what* the code
should look like, not the current state or any in-flight migration steps.

## Two tiers of types

Authored files (YAML / Cooklang) are raw material, not the objects the system
reasons about. Every domain concept therefore has two shapes:

| concept | DTO (authored, validated) | enriched value (public, frozen) |
| :--- | :--- | :--- |
| ingredient | `_IngredientData` (private) | `Ingredient` |
| recipe | `Recipe` (the authored document) | `PreparedRecipe` |

- **DTO** — schema fields + shape validation only. It decodes YAML/Cooklang and
  carries raw authored values. It is not a public abstraction; for the
  ingredient it is private (`_IngredientData`).
- **Enriched value** — everything a downstream consumer needs, computed once and
  frozen. Immutable. This is the public building block.

Enrichment is a service:

- `prepare_ingredient(dto, units) -> Ingredient`
- `prepare_recipe(recipe, catalog) -> PreparedRecipe`

Only the enrichment service ever touches a DTO; nobody downstream does.

## Model purity

- A model may own logic that is a pure function of its own fields (shape
  validation, derived values computed from its own fields alone).
- A model must not own logic that needs a collaborator (a registry, the
  conversion graph, another model), I/O, or orchestration across objects.

Because enrichment resolves collaborators *before* construction, methods that
would be impure on the DTO (e.g. `convert`) become pure on the enriched value —
the graph they need is already a frozen field.

## Public vs private API

- Privacy in Python is a convention, not enforcement: a single leading
  underscore means "internal, not part of the public API." The declaration of
  intent, combined with the package `__all__`, defines the public surface.
- The public ingredient is `Ingredient` (enriched, frozen). Its DTO
  (`_IngredientData`) is deliberately excluded from the public surface: it is a
  parse shim, not a building block.
- Recipes differ: the authored `Recipe` *is* a public object (it is the authored
  document, with a legitimate standalone consumer), and `PreparedRecipe` is its
  enriched, computed form.

## Conversion graph

Every enriched `Ingredient` carries its own full, frozen conversion graph.

Edges come from four sources:

1. the package edge: `container -> package.unit = amount`
2. authored `conversions`: `from -> to = factor`
3. universal physics: mass -> `g`, volume -> `ml`
4. synonyms: `alias -> canonical = 1.0`, from the YAML that owns them

- **Synonyms are edges, not a lookup function.** `units.yaml` registers aliases
  explicitly; ingredient-specific aliases are registered in the ingredient YAML.
- **No runtime normalization.** `Ingredient.convert(amount, from, to)` is
  literally `graph.convert(...)`. Pure, no registry at call time.

## Custom units

An ingredient declares its non-standard units explicitly:

```yaml
custom_units: [clove, head]
conversions:
  - {from: clove, to: g, factor: 3.0}
  - {from: head,  to: g, factor: 50.0}
```

Rules:

- Every `conversions` / `package.unit` endpoint must be a **standard unit**, a
  **packaging container**, or a **declared custom unit**.
- **Gram reachability is required.** A custom unit not bridged (directly or
  transitively) to grams is a validation error. A declared node with no edges is
  legal only until it fails this check.
- The centralized `count` dimension is removed; its units become
  ingredient-local custom units (`piece`, `item`, `head`, `clove`). `slice` and
  `bunch` vanish; `bunch` survives only as a container.

## Validation strategy: fail fast

- **DTO validation** runs at YAML/parse time (shape only).
- **Ingredient enrichment** runs the full validation (graph invariants,
  registered-container check, custom-unit grammar, gram reachability) and fails
  the moment it runs.
- **Recipe validation is trivial**: ingredient enrichment already guarantees
  gram reachability for every registered unit, so a recipe only checks that it
  references existing ingredients using registered units.

## Recipe computation (the enriched result)

`PreparedRecipe` pre-computes everything a consumer needs:

- batch grams, cooked grams, cooking loss
- per-ingredient breakdown: grams used, cost, macro contribution
- batch + per-serving macros
- **duplicate ingredients are merged** (an ingredient appearing in different
  units is summed to grams, then re-expressed in one unified unit).
- amounts are represented in the **package unit** by default.

## The goal the design serves

The system has one narrow product goal: turn authored `.cook` recipes into
standalone HTML recipe cards. The architecture above (DTO -> enrichment ->
frozen values) is the shape that goal naturally produces, and it is also the
shape a future planner/shopping-list feature would consume, since the enriched
values are stable, fully-resolved inputs with no hidden state.
