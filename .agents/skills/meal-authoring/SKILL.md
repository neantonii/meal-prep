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

### 1. Zero Silent Additions & One-at-a-Time Reconciliation
* NEVER silently fabricate, assume, or add ingredients to `data/ingredients/`.
* **Resolved Staples (FYI):** Before prompting for missing items, list all ingredients that were found and resolved in the catalog in a single concise line (no confirmation required).
* **Loop Over Missing Items One at a Time:**
  * For each missing ingredient, prompt the user for the essential retail purchase details: **Product title/brand, retail CAD price, and net package amount/mass** (e.g. copied from Voilà or grocery store).
  * If the user supplies no nutrition facts, ask a single quick confirmation: *"Any nutrition facts on the package, or should I pull standard USDA biological norms?"*
  * If USDA is approved, fetch and populate values behind the scenes. **Never print walls of USDA nutrient numbers into chat.**
  * Once an item is resolved, move immediately to the next missing item until all are completed.

### 2. Zero-Echo Policy & Canvas Card Presentation
* **Never dump walls of text into chat:** Do NOT print the raw `.cook` file contents, markdown recipe tables, or raw terminal math audits. The rendered recipe card already conveys all necessary information.
* **Drive the Canvas UI:**
  * Run deterministic math review and tests silently in the terminal.
  * Generate HTML recipe cards:
    ```bash
    PYTHONPATH=src python3 -c 'from meal_prep.renderer import render_all_recipe_cards; render_all_recipe_cards()'
    ```
  * Immediately show the rendered visual card in Canvas using:
    `canvas_ui_control(command="show_preview", path="recipe_cards/<category>/<recipe-slug>.html")`
  * Accompany the preview with a brief 1–2 sentence chat message asking for the user's review (concisely highlighting any macro outlier if present).

### 3. Human-in-the-Loop & Commit Policy
* Work methodically on one meal at a time.
* Do not edit or create repository files during brainstorming until the user explicitly approves the recipe design.
* Keep draft files in the working directory. Stage and commit ONLY AFTER the user gives explicit final approval.

### 4. Culinary Usability on First Pass
* Audit measurement units in the recipe body on the very first draft to reflect intuitive home cooking:
  * Prefer volumetric spoons (`0.5 tsp`, `1 tsp`, `1 tbsp`) over awkward gram weights (`4.7 g`, `5 g`) for fats, dairy, and condiments.
  * Prefer standard cups or spoons (`0.33 cup`, `0.5 cup`) over awkward gram weights (`63 g`) for dry grains.
  * Prefer `0.25 tsp`, `0.5 tsp`, `1 tsp` over fractional grams for spices.
  * Use mass `g` or discrete counts (`piece`, `clove`) for bulk proteins and large produce.
* Ensure all chosen units convert cleanly to grams via `ConversionGraph` or universal units in `data/units.yaml`.

### 5. Untracked Water Policy
* Water is strictly untracked as an ingredient token: do NOT tag water with `@water` or `@tap-water`.
* Specify the exact liquid cooking volume in the step instructions (e.g., *"combine 120 ml (1/2 cup) cold water and..."*).

### 6. File Touch Boundaries
* Limit edits during meal authoring to:
  * Target recipe file: `recipes/<category>/<recipe-slug>.cook`
  * Target ingredient file: `data/ingredients/<aisle>.yaml`
  * Read-only references: `data/equipment.yaml`, `data/units.yaml`, `data/aisles.yaml`, `src/meal_prep/models/enums.py`, `MEALS.md`, `INGREDIENTS.md`.

---

## Step-by-Step Authoring Sequence

### Step 1: Interactive Concept Alignment
Discuss and align on target category, portion count, raw vs. cooked target weights, technique, and cookware (must match canonical items in `data/equipment.yaml`). Do not create or edit files during this step.

### Step 2: Ingredient Reconciliation (FYI + One-at-a-Time Loop)
1. Report resolved staples in a single FYI line: *"Resolved in catalog: olive-oil, kosher-salt, black-pepper."*
2. If any ingredients are missing, prompt for each missing item individually (product title, price, package size).
3. If nutrition facts are omitted, confirm USDA lookup, populate silently, and advance to the next missing item.
4. Add confirmed entries to `data/ingredients/<aisle>.yaml`.

### Step 3: Author the `.cook` Recipe File
Write `recipes/<category>/<recipe-slug>.cook`:
1. Include YAML frontmatter (`id`, `title`, `category`, `yield`, `storage`, `equipment`).
2. Write sequential instructions using `@ingredient{qty%unit}`, `#equipment`, and `~timer{duration%unit}`.
3. Apply culinary usability on first pass (spoons/cups for fats, condiments, spices, and grains).
4. Follow the untracked water rule.

### Step 4: Silent Math Review & Test Verification
1. Silently inspect the math audit:
   ```bash
   PYTHONPATH=src python3 -c 'from meal_prep.library import MealPrepLibrary; print(MealPrepLibrary.load().review_math("<recipe-slug>"))'
   ```
2. **Outlier Assessment:** Compare per-portion macros against the category benchmarks in `MEALS.md`. If macros fall outside expected ranges (e.g. protein too low, calories significantly out of range), flag the specific outlier and prepare a concise adjustment suggestion.
3. Silently run the automated test suite:
   ```bash
   PYTHONPATH=src python3 -m pytest tests/
   ```

### Step 5: Render Card & Present via Canvas Preview
1. Render HTML recipe cards:
   ```bash
   PYTHONPATH=src python3 -c 'from meal_prep.renderer import render_all_recipe_cards; render_all_recipe_cards()'
   ```
2. Verify that `recipe_cards/<category>/<recipe-slug>.html` exists.
3. Call `canvas_ui_control(command="show_preview", path="recipe_cards/<category>/<recipe-slug>.html")`.
4. In chat, output a concise 1–2 sentence message notifying the user that the card is ready for review. If an outlier was flagged in Step 4, concisely note it with the suggested adjustment. Do not echo code or math tables.
