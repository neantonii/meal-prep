---
name: meal-authoring
description: This skill should be used when the user asks to "add a meal", "add a recipe", "new recipe", "import recipe", "brainstorm a meal", "author a recipe", or mentions adding batch-cooked meal prep recipes.
---

# Meal Authoring Skill

This skill guides the interactive authoring, ingredient reconciliation, math auditing, and card generation for modular Cooklang recipes.

Follow the canonical specifications in **`MEALS.md`** and **`INGREDIENTS.md`**.

---

## Canonical Taxonomy & Standards Reference

To prevent drift over time, canonical sets are not hardcoded. When authoring recipes or ingredients, read and inspect the single-source-of-truth files directly:

| Standard / Taxonomy | Authoritative Source File | Inspection Purpose |
| :--- | :--- | :--- |
| **`RecipeCategory` & `StorageType`** | `src/meal_prep/models/enums.py` | Allowed recipe categories and ingredient storage modes |
| **Aisle Taxonomy** | `data/aisles.yaml` | Valid aisle slugs and walking order |
| **Cookware & Equipment Tokens** | `data/equipment.yaml` | Canonical cookware IDs and recognized aliases |
| **Units & Packaging Containers** | `data/units.yaml` | Allowed continuous units, discrete units, and packaging containers |

---

## Core Guardrails

### 1. Zero Silent Additions (Zero Guesswork)
* NEVER silently fabricate, assume, or add ingredients to `data/ingredients/`.
* If any ingredient or cookware is missing, halt immediately and ask the user for purchase details (store/brand, package size, price in CAD, label nutrition).
* Cross-check nutritional values against USDA FoodData Central behind the scenes to verify biological norms and fill in omitted label micronutrients (potassium, sodium, saturated fat). Alert the user only on significant (>15%) deviations.

### 2. Human-in-the-Loop & Commit Policy
* Work methodically on one meal at a time.
* Do not edit or create repository files during brainstorming until the user explicitly approves the recipe design.
* Keep draft files in the working directory. Stage and commit ONLY AFTER the user gives explicit final approval.

### 3. Culinary Usability & Practical Measurement Units
* Audit measurement units in the recipe body to ensure they reflect intuitive home cooking:
  * Prefer volumetric spoons (`1 tsp`, `1 tbsp`) over awkward gram weights (`4.7 g`, `5 g`) for fats, dairy, and condiments.
  * Prefer standard cups or spoons (`0.33 cup`, `0.5 cup`) over awkward gram weights (`63 g`) for dry grains.
  * Prefer `0.25 tsp`, `0.5 tsp`, `1 tsp` over fractional grams for spices.
  * Use mass `g` or discrete counts (`piece`, `clove`) for bulk proteins and large produce.
* Ensure all chosen units convert cleanly to grams via `ConversionGraph` or universal units in `data/units.yaml`.

### 4. Untracked Water Policy
* Water is strictly untracked as an ingredient token: do NOT tag water with `@water` or `@tap-water`.
* Specify the exact liquid cooking volume in the step instructions (e.g., *"combine 120 ml (1/2 cup) cold water and..."*).

### 5. File Touch Boundaries
* Limit edits during meal authoring to:
  * Target recipe file: `recipes/<category>/<recipe-slug>.cook`
  * Target ingredient file: `data/ingredients/<aisle>.yaml`
  * Read-only references: `data/equipment.yaml`, `data/units.yaml`, `data/aisles.yaml`, `src/meal_prep/models/enums.py`, `MEALS.md`, `INGREDIENTS.md`.

---

## Step-by-Step Authoring Sequence

### Step 1: Interactive Brainstorming & Review
Discuss and align on:
1. Target category (`modular_protein`, `modular_carb`, `modular_cooked_veg`, `fresh_salad_veg`, `breakfast`).
2. Portion count and cooked weight target (e.g. 1 serving @ 185 g cooked).
3. Raw batch weight vs. expected cooked weight.
4. Ingredients list, spice mix, and culinary technique.
5. Cookware (must match canonical items in `data/equipment.yaml`).

*Do NOT create or modify files during Step 1 until the user approves.*

### Step 2: Ingredient Reconciliation
1. Cross-reference every ingredient against `data/ingredients/<aisle>.yaml`.
2. If missing: pause and request user's purchase details.
3. Once provided, cross-check against USDA FoodData Central behind the scenes.
4. Add confirmed entries to `data/ingredients/<aisle>.yaml` following `INGREDIENTS.md`.

### Step 3: Author the `.cook` Recipe File
Write `recipes/<category>/<recipe-slug>.cook`:
1. Include complete YAML frontmatter (`id`, `title`, `category`, `yield`, `storage`, `equipment`).
2. Write sequential instructions using `@ingredient{qty%unit}`, `#equipment`, and `~timer{duration%unit}`.
3. Follow the untracked water policy.

### Step 4: Culinary Usability & Measurement Units Audit
Verify all ingredient tags use sensible, human-friendly units (spoons, cups, pieces) instead of awkward precision gram numbers.

### Step 5: Macro Alignment & Comparative Audit
Compute per-portion macros and compare against category peers or benchmarks in `MEALS.md`. Flag significant outliers to the user with suggested adjustments.

### Step 6: Automated Verification & Math Review
1. Inspect the deterministic math audit:
   ```bash
   PYTHONPATH=src python3 -c 'from meal_prep.library import MealPrepLibrary; print(MealPrepLibrary.load().review_math("<recipe-slug>"))'
   ```
2. Run the automated test suite:
   ```bash
   PYTHONPATH=src python3 -m pytest tests/
   ```

### Step 7: HTML Recipe Card Generation
1. Render HTML recipe cards:
   ```bash
   PYTHONPATH=src python3 -c 'from meal_prep.renderer import render_all_recipe_cards; render_all_recipe_cards()'
   ```
2. Verify that `recipe_cards/<category>/<recipe-slug>.html` was generated and exists.
3. Present the recipe summary, math audit, and portion scale weight to the user for final review and approval.
