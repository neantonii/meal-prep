# AGENTS.md — Developer & AI Agent Handbook

This handbook serves as the primary persistent context for developers and AI agents working on the Meal Prep codebase.

---

## 1. System Architecture & Separation of Concerns

The Meal Prep system uses a file-based, deterministic architecture with zero external database dependencies:

* **Taxonomy & Standards:** `data/aisles.yaml`, `data/units.yaml`, `data/equipment.yaml`.
* **Domain Enums & Models:** `src/meal_prep/models/` (`StorageType`, `RecipeCategory`, `ConversionGraph`). Built on Pydantic v2.
* **Ingredients Catalog:** Partitioned into 7 aisle YAML files in `data/ingredients/<aisle>.yaml`.
* **Modular Recipes:** Stored as independent Cooklang files in `recipes/<category>/<recipe-slug>.cook`.
* **Deterministic Calculation:** `src/meal_prep/calculator.py` computes all batch weights, moisture loss, per-serving macros, and retail costs on the fly.
* **Visual Rendering:** `src/meal_prep/renderer.py` compiles recipes into standalone HTML cards.

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
