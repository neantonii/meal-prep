# Conversions Reference

Authoring rules for the per-ingredient conversion graph. The engine contract
lives in code — read it there, not here:

- Graph model and structural invariants (`build_graph` rejects): module
  docstring of `src/meal_prep/engines/conversion_graph.py`.
- Synonym resolution, universal physics edges, and gram-reachability checks
  (`package`, every custom unit, the macros basis): module docstring and
  `ValueError`s of `src/meal_prep/services/ingredients.py`
  (`prepare_ingredient`).
- Reserved `package`/`count` nodes (no universal edges; every meaning is
  ingredient-authored): `data/units.yaml`.

## Authoring Rules

- Weigh, do not look up. `1 cup flour = 120 g` varies by ingredient; the factor
  belongs to this entry, measured for this product. An unweighed factor is a
  guess: stage it and flag it yellow on the review card.
- One edge per fact. `package -> g = 454` for a 454 g pack; `count -> g` from
  weighing N pieces and dividing. Author the `package` edge in the
  friendliest standard unit: the largest unit (`kg` over `g`, `l` over
  `ml`) that keeps the factor ≥ 1 and < 1000 and matches how the pack is
  sold (`package -> l = 4` for a 4 L jug, never `package -> ml = 4000`).
- Keep chains minimal: `package -> count -> g` covers count-based recipes and
  pricing in two edges. Add `cup -> g` only when recipes or the macros basis
  need cups.
- Macros-basis coupling: when the label reads `per 1/3 cup`, set
  `macros: {unit: cup, amount: 0.333}` and ensure `cup -> g` exists.
  Enrichment computes `basis_g = convert(amount, basis, g)`, `scale =
  100 / basis_g`.
- Confirm recipe units at review time (`cup, tbsp, count, piece, ...`) and
  author each one now — every unit a recipe will use must reach `g`.
