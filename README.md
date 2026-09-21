# Meal Prep

An intelligent meal prep data normalization, indexing, and meal planning system built in Python.

## Overview

The core goal of this project is to take structured, batch-cooked recipes and ingredients and transform them into a fully normalized, queryable, and automated meal planning engine.

### Project Roadmap & Core Pillars

1. **Data Normalization:**
   * Parse and extract structured recipe data into normalized data models (recipes, ingredients, macronutrients, unit pricing, aisle taxonomy, and preparation metadata).
   * Ensure consistent units of measure, yields, cooking methods, and grocery price references.

2. **Indexing & Search:**
   * Build indexing and querying capabilities across multiple dimensions:
     * **Macronutrient profiles** (calories, protein, fat, carbohydrates, fiber)
     * **Aisle taxonomy** (*Meat & Seafood, Produce, Frozen, Dairy & Refrigerated, Pantry, Spices, Bakery*)
     * **Cost per serving** and batch preparation cost
     * **Equipment and shelf-life constraints** (e.g., freezer-friendly, air fryer, quick prep)

3. **Meal Planning Engine:**
   * Compose modular meal combinations (protein + side + fresh veg) to meet daily/weekly macro targets and budget constraints.
   * Generate consolidated, aisle-sorted grocery shopping lists based on selected weekly meal plans.
   * Automate batch cooking schedules and prep workflow optimization.

---

## System Architecture

* **File-Based Architecture:** Everything lives in plain text YAML and Cooklang (`.cook`) files. There is no external database or hidden state.
* **Separation of Concerns:**
  * **Taxonomy & Standards:** `data/aisles.yaml`, `data/units.yaml`, `data/equipment.yaml`.
  * **Domain Enums & Models:** `src/meal_prep/models/` (Pydantic models, unit conversion graph).
  * **Ingredients Catalog:** Partitioned into 7 aisle files in `data/ingredients/<aisle>.yaml`.
  * **Modular Recipes:** Partitioned into 5 category folders in `recipes/<category>/<recipe-slug>.cook`.
  * **Deterministic Calculation:** `src/meal_prep/calculator.py` derives all macros, weights, moisture loss, and costs on the fly.
  * **Visual Presentation:** `src/meal_prep/renderer.py` compiles recipes into standalone HTML cards.

---

## Developer Quickstart & Command Reference

All Python commands assume `PYTHONPATH=src`:

### Running Tests
Execute the full test suite (frontmatter validation, ingredient resolution, unit conversions, and equipment registry):
```bash
PYTHONPATH=src python3 -m pytest tests/
```

### Reviewing Recipe Math & Macros
Audit a recipe's batch totals, cooking loss, portion weight, macros, and cost:
```bash
PYTHONPATH=src python3 -c 'from meal_prep.library import MealPrepLibrary; print(MealPrepLibrary.load().review_math("<recipe-slug>"))'
```
Or use the CLI:
```bash
PYTHONPATH=src python3 -m meal_prep.cli audit <category> <recipe-slug>
```

### Rendering HTML Recipe Cards
Generate visual, standalone recipe cards for all recipes (stored in `recipe_cards/`):
```bash
PYTHONPATH=src python3 -c 'from meal_prep.renderer import render_all_recipe_cards; render_all_recipe_cards()'
```

---

## Documentation Index

* **[MEALS.md](MEALS.md)** — Modular recipe specification, Cooklang syntax, step-by-step authoring workflow, macro benchmarks, and authoring guardrails.
* **[INGREDIENTS.md](INGREDIENTS.md)** — Ingredient catalog schema, package units, reference pricing, and USDA FoodData Central validation standards.
* **[AGENTS.md](AGENTS.md)** — Developer & AI agent handbook for persistent repository context, file boundaries, and operational protocols.
