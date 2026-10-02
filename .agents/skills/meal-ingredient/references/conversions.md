# Conversions Reference

How the per-ingredient conversion graph is built and what paths enrichment
requires. Engine: `meal_prep.engines.conversion_graph` (dependency-free).
Service: `meal_prep.services.ingredients.prepare_ingredient`.

## Mental Model

- Edge `A -> B = factor` means `1 A = factor B`s. Reverses derive automatically.
- Synonym map first: every `units.yaml` noun (canonical + aliases) resolves to
  canonical; then `custom_units` register, rejecting any noun collision.
- Authored edges resolve through synonyms, join universal physics edges
  (`kg -> g`, `tbsp -> ml`, ...), and feed `build_graph`.
- `package` and `count` are reserved nodes with no universal edges. Every
  `package -> ...` meaning lives on the ingredient.

## Required Paths

Enrichment fails (`ValueError`) unless all hold:

1. `package -> g` reachable. Always author a `package` edge with the weighed
   pack size. Direct (`package -> g`) or chained (`package -> count -> g`,
   `package -> head -> g`) both satisfy.
2. Every `custom_units` canonical `-> g` reachable. Each custom noun needs its
   own weighed edge.
3. Macros basis `-> g` reachable. When the label basis is `g`, trivially true.
   When the basis is `cup`/`tbsp`/custom, author that edge too (e.g. frozen
   corn: `cup -> g = 145` doubles as recipe unit and macros basis).
4. Every unit a recipe will use `-> g` reachable. Ask upfront which units the
   calling recipe needs; author each one now.

## Graph Invariants (build_graph rejects)

- Factor positive finite (`> 0`, no bool, no NaN/inf). YAML `yes/no` decode to
  bool — never use them as factors.
- Endpoints distinct non-empty tokens. `from == to` after cleanup fails
  (`UnitConversion.validate_different_units`).
- At most one edge per ordered pair; reverse pairs rejected (derived
  automatically). Duplicate `tbsp -> g` plus `g -> tbsp` fails.
- Undirected acyclicity. The unordered edge set must be a forest. A diamond
  (`cup -> ml`, `ml -> g`, `cup -> g`) fails — keep the two-hop path, drop the
  shortcut. Prefer chains through `g` or `ml` over redundant direct edges.
- Custom-unit noun collision. A custom canonical or alias matching any
  registered noun (`g`, `cup`, `package`, `count`, earlier custom) fails.
  Never shadow `package` or `count` with a custom unit.

## Authoring Rules

- Weigh, do not look up. `1 cup flour = 120 g` varies by ingredient; the factor
  belongs to this entry, measured for this product.
- One edge per fact. `package -> g = 454` for a 454 g pack; `count -> g` from
  weighing N pieces and dividing.
- Keep chains minimal: `package -> count -> g` covers count-based recipes and
  pricing in two edges. Add `cup -> g` only when recipes or the macros basis
  need cups.
- Macros-basis coupling: when the label reads `per 1/3 cup`, set
  `macros: {unit: cup, amount: 0.333}` and ensure `cup -> g` exists.
  Enrichment computes `basis_g = convert(amount, basis, g)`, `scale =
  100 / basis_g`.
