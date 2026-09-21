# Meal Prep

An intelligent meal prep data normalization, indexing, and meal planning system built in Python.

## Overview

The core goal of this project is to take structured, batch-cooked recipes from our markdown recipe book and transform them into a fully normalized, queryable, and automated meal planning engine.

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

## Repository Structure

```
meal-prep/
├── data/
│   ├── aisles.yaml                     # Grocery store aisle definitions & order
│   ├── equipment.yaml                  # Canonical cookware items & aliases
│   ├── units.yaml                      # Universal unit conversions & packaging types
│   └── ingredients/                    # 7 aisle-partitioned ingredient catalog files
│       ├── bakery.yaml
│       ├── dairy.yaml
│       ├── meat.yaml
│       ├── pantry.yaml
│       ├── produce.yaml
│       ├── seafood.yaml
│       └── spices.yaml
├── recipes/                            # Modular Cooklang recipe files (.cook)
│   ├── modular_protein/
│   ├── modular_carb/
│   ├── modular_cooked_veg/
│   ├── fresh_salad_veg/
│   └── breakfast/
├── src/meal_prep/
│   ├── models/                         # Domain Pydantic models & validation
│   ├── library.py                      # MealPrepLibrary (single-line workspace loader)
│   ├── calculator.py                   # Math, macros, yield, and cost calculator
│   └── renderer.py                     # HTML recipe card generator (isolated)
├── tests/                              # Automated test suite (pytest)
├── schemas/                            # JSON schemas for validation
├── INGREDIENTS.md                      # Ingredient authoring guidelines & schema spec
└── MEALS.md                            # Recipe authoring guidelines & Cooklang syntax
```

---

## Workflow: Adding a New Meal

When adding or importing a meal, follow this strictly sequenced 4-phase protocol:

### Phase 1: Interactive Brainstorming & Review
* Discuss the meal concept with the user before touching any files:
  * Portion target and number of servings (e.g. 4 servings).
  * Target cooked weight per portion (e.g. 165g) and raw batch weight.
  * Ingredients list and spice mix.
  * Technique and required equipment (must exist in `data/equipment.yaml`).
* **Rule:** Do NOT edit or create any repository files during Phase 1 until the user explicitly approves the design.

### Phase 2: Ingredient Reconciliation
* Audit the approved ingredients against `data/ingredients/`:
* **CRITICAL RULE: ZERO GUESSWORK — NO SILENT INGREDIENT CREATION**
  * The agent must **NEVER** silently create, assume, or fabricate ingredients in `data/ingredients/`.
  * If an ingredient is missing, halt and ask the user for purchase details (store, brand, package amount/unit, price). Never guess prices or nutritional profiles to make a test pass.
  * Once the user provides or approves reference details, silently cross-check nutrients against USDA FoodData Central biological norms and fill in any omitted label micronutrients (sodium, potassium, saturated fat).
  * Consult `INGREDIENTS.md` for schema rules (bidirectional explicit conversions: `{from: ..., to: ..., factor: ...}`).

### Phase 3: Recipe Authoring (`.cook`)
* Write the recipe to `recipes/<category>/<recipe-slug>.cook`.
* Consult `MEALS.md` for frontmatter requirements (`id`, `title`, `category`, `yield`, `storage`, `equipment`) and Cooklang syntax (`@ingredient{qty%unit}`, `#equipment`, `~timer{duration%unit}`).

### Phase 4: Math Review & Verification
* Review the math using the calculator (do not read the renderer):
  ```bash
  PYTHONPATH=src python3 -c 'from meal_prep.library import MealPrepLibrary; print(MealPrepLibrary.load().review_math("<recipe-slug>"))'
  ```
* Present the math audit table to the user for review (grams converted, batch totals, cooking loss %, portion scale weight, cost, and macros).
* Run the test suite:
  ```bash
  PYTHONPATH=src python3 -m pytest tests/
  ```
* Render HTML recipe cards if requested:
  ```bash
  PYTHONPATH=src python3 -c 'from meal_prep.renderer import render_all_recipe_cards; render_all_recipe_cards()'
  ```

---

## ⚠️ AGENT BOUNDARIES: Strict File Scope & Anti-Browsing Directives

To conserve context tokens and prevent hallucinations, agents working on adding meals or maintaining data **MUST strictly obey the following file access boundaries**:

### ✅ Files the Agent Is Allowed to Touch / Inspect:
When adding or editing a meal, the agent should **only** access these specific files:
1. **Target Recipe File:** `recipes/<category>/<recipe-slug>.cook` (create or edit).
2. **Relevant Ingredient File(s):** `data/ingredients/<aisle>.yaml` (ONLY the specific aisle file for an ingredient being added/checked).
3. **Equipment Registry:** `data/equipment.yaml` (read-only to verify cookware tokens, or edit ONLY if a new approved cookware item is introduced).
4. **Units Registry:** `data/units.yaml` (read-only to verify unit names, aliases, and container nouns).
5. **Guidelines:** `INGREDIENTS.md` and `MEALS.md` (read-only reference for schemas and formatting).

### ❌ Files the Agent Must NOT Load or Browse:
1. **DO NOT load or inspect `src/meal_prep/renderer.py`:**
   * This is a large file (~23 KiB) containing pure HTML and CSS template rendering logic.
   * It does **not** contain recipe math, models, or data.
   * Reading it wastes thousands of tokens. The renderer consumes `PreparedRecipe` in one line automatically.
2. **DO NOT randomly browse or modify `src/meal_prep/models/*.py`:**
   * `recipe.py`, `ingredient.py`, `conversion_graph.py`, `units.py`, `equipment.py`, `aisle.py`, and `enums.py` are stable, fully-tested core infrastructure.
   * Do not open or alter them during normal meal authoring.
3. **DO NOT browse or modify `tests/*.py`:**
   * Test files are for test execution (`pytest tests/`). Do not open or modify them when authoring recipes.
4. **DO NOT load unrelated ingredient files:**
   * If working on a chicken recipe, do not open `seafood.yaml`, `dairy.yaml`, or `bakery.yaml`. Only open `meat.yaml` and/or `spices.yaml` if an approved item needs adding.
5. **DO NOT open other recipe files just to "see examples":**
   * Reference examples are already documented in `MEALS.md`.
   * To inspect macros of existing meals for peer comparison, run `MealPrepLibrary.load()` via a python one-liner rather than loading multiple raw `.cook` files into context.


