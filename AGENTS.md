# AGENTS.md — Developer & AI Agent Handbook

This handbook serves as the primary persistent context for developers and AI agents working on the Meal Prep codebase.

---

## 1. System Architecture & Separation of Concerns

The Meal Prep system uses a file-based, deterministic architecture with zero external database dependencies.

### Layers (top to bottom)

1. **Data** — YAML standards and catalogs: `data/units.yaml` (unit taxonomy), `data/aisles.yaml`, `data/equipment.yaml`, `data/ingredients/<aisle>.yaml`, `recipes/<category>/<slug>.cook`.
2. **Engines (pure kernels)** — `src/meal_prep/engines/` (stdlib-only, no domain imports): the conversion graph, and future pure kernels such as the LP planner's solver.
3. **Domain models** — `src/meal_prep/models/` (Pydantic v2): `Ingredient`, `Recipe`, `UnitsRegistry`, `EquipmentRegistry`. May depend on `engines`, never the reverse.
4. **Adapters (I/O)** — `src/meal_prep/adapters/`: the only code that reads files or parses formats (YAML taxonomies, `.cook` recipes). Adapters construct models; models never construct themselves from files.
5. **Calculation** — `src/meal_prep/calculator.py` (`prepare_recipe` → `PreparedRecipe`) computes batch weights, moisture loss, per-serving macros, and retail costs.
6. **Library/gateway** — `src/meal_prep/library.py` (`MealPrepLibrary`) loads + cross-validates everything via adapters and exposes `prepare()`.
7. **Presentation** — `src/meal_prep/renderer.py` (HTML cards) and `PreparedRecipe.review_math()` (text audit). **Rounding belongs only here.**

Dependency direction (a layer may depend on anything below it, never above):
`engines ← models ← adapters ← library ← renderer`, with `calculator` a service over `models`/`engines` composed by `library`. `services/` (business logic) slots in beside `calculator` once extracted.

### Model purity rule

> **A model may own logic that is a pure function of its own fields and needs no
> external context. It must not own logic that requires collaborators.**

Concretely, a Pydantic model may hold:
* field-level validation (data shape correctness), and
* derived values computed from its own fields alone (e.g. a `total` from a `list`).

A model must **not** hold:
* methods/properties that need another model, a registry, or a service (e.g. price
  per 100 g, which needs the conversion graph + units registry);
* I/O, parsing, or persistence (YAML/recipe loading) — those are adapters;
* orchestration across multiple objects — that is a service;
* presentation/formatting (rounding, HTML, human labels) — that is the presentation layer.

When behaviour needs a collaborator, extract it into `services/` (business logic) or
`adapters/` (I/O), taking the model as an argument, rather than growing methods on the model.

### The conversion graph is a standalone, dependency-free engine

`src/meal_prep/engines/conversion_graph.py` is the single source of truth for unit conversion. It
imports **nothing** from the rest of the codebase (stdlib only), and must stay that way — a drift
guard test (`test_engines_package_has_no_domain_imports`) fails if any ``engines`` module adds a
domain import. This package is the home for future pure kernels (e.g. the LP planner's solver core).

Its contract, documented in the module docstring:
* It operates on opaque unit **tokens** (strings) and directed **edges** (`source -> target = factor`).
* It enforces: positive finite factors, no self-loop, one edge per unordered pair (repeats and
  reverses are errors), no directed cycle, and full immutability of the result.
* It does **no rounding** and does **no unit-name normalization** — both are the caller's job. The
  domain adapter (`_build_ingredient_graph` in `ingredient.py`) normalizes names via
  `UnitsRegistry.normalize_token` and reduces an ingredient to a list of `ConversionEdge`s before
  calling `build_graph`.


---

## 2. Core Operational Tasks & Skills

### Task A: Software Development & Maintenance
When developing features, refactoring, fixing bugs, or maintaining the engine:
* **Scope:** `src/meal_prep/`, `tests/`, `schemas/`.
* **Standards:**
  * Idiomatic Python 3.13 and strict Pydantic v2 models.
  * Deterministic math (no floating point drift or ungrounded assumptions).
  * Maintain 100% test pass rate (`PYTHONPATH=src pytest tests/`).
  * Preserve backward compatibility for existing ingredient YAMLs and `.cook` recipes.

### Task B: Meal & Recipe Authoring
When adding, authoring, brainstorming, or importing recipes:
* Use the **`meal-authoring` skill** (`.agents/skills/meal-authoring/SKILL.md`).
* Consult **`MEALS.md`** for the complete specification, syntax, culinary unit rules, and category macro benchmarks.
* Consult **`INGREDIENTS.md`** for ingredient schemas, reference products, and USDA cross-validation.

---

## 3. General Development Protocols & Safeguards

1. **Human-in-the-Loop & Commit Policy:**
   * Keep work in progress in the working directory while drafting and refining.
   * Stage and commit only after verifying with tests and receiving user confirmation.
   * Never push to remote branches or open pull requests unless explicitly instructed.
2. **Deterministic Data Integrity:**
   * All macros, costs, and conversions must derive deterministically from the ingredient catalog and unit conversion graphs. Never hardcode computed numbers into data files.

---

## 4. Verification Commands

Always run verification before concluding tasks:

* **Full Automated Test Suite:**
  ```bash
  PYTHONPATH=src python3 -m pytest tests/
  ```
* **Recipe Math Audit:**
  ```bash
  PYTHONPATH=src python3 -c 'from meal_prep.library import MealPrepLibrary; print(MealPrepLibrary.load().review_math("<recipe-slug>"))'
  ```
* **Render All Recipe Cards:**
  ```bash
  PYTHONPATH=src python3 -c 'from meal_prep.renderer import render_all_recipe_cards; render_all_recipe_cards()'
  ```
