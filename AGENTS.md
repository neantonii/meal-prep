# AGENTS.md — Meal Prep System Developer & Agent Handbook

This handbook serves as the primary persistent context for all AI agents working in this repository. Follow these conventions and workflows strictly.

---

## 1. System Architecture & Philosophy

* **File-Based Architecture:** Everything lives in plain text/YAML and Cooklang files. There is no database or hidden state.
* **Separation of Concerns:**
  * **Taxonomy & Standards:** `data/aisles.yaml`, `data/units.yaml`, `data/equipment.yaml`.
  * **Domain Enums:** `src/meal_prep/models/enums.py` (`StorageType`, `RecipeCategory`).
  * **Ingredients Catalog:** Partitioned into 7 aisle files in `data/ingredients/<aisle>.yaml`.
  * **Recipes:** Partitioned into modular `.cook` files in `recipes/<category>/<recipe-slug>.cook`.
  * **Validation & Testing:** Pydantic models in `src/meal_prep/models/` and automated tests in `tests/`.

---

## 2. Interactive Workflow: Adding a New Meal

When the user asks to add or brainstorm a new meal, execute the following 4-step protocol:

### Phase 1: Interactive Brainstorming & Review
* Discuss the recipe concept with the user:
  * Servings and portion targets.
  * Raw batch weight vs cooked serving weight.
  * Ingredients, spice mix, and technique.
  * Required equipment (matching canonical cookware in `data/equipment.yaml`).
* **Rule:** Do NOT edit or create any repository files during Phase 1 until the user explicitly approves the recipe design.

### Phase 2: Ingredient Reconciliation
* Audit the approved ingredients against the catalog in `data/ingredients/`:
  * Check each ingredient to see if a canonical staple already exists.
* **CRITICAL DATA INTEGRITY & CROSS-VALIDATION RULE:**
  * **NEVER invent, guess, or estimate ingredient data** (macros, packaging weights, or prices).
  * **Prompt the user explicitly** to supply the missing information from their real purchases (product name, price, package mass, label nutrition facts).
  * **Always cross-validate against USDA FoodData Central:**
    * Cross-check the user-supplied label facts against the USDA benchmark.
    * Check if missing or zero values make biological sense (e.g. 0g carbs/sugars is natural for raw chicken breast, but 0mg potassium or sodium is suspicious).
    * **No Spamming Rule:** If all fields align with USDA, simply state that validation passed. Only alert the user and display numbers if a field is suspicious, missing, or deviates by >15%.
* Follow the authoring guidelines in `INGREDIENTS.md`.
* Present the proposed YAML snippet and validation report to the user for review before writing it to `data/ingredients/<aisle>.yaml`.

### Phase 3: Recipe File Authoring
* Follow the authoring guidelines in `MEALS.md`.
* Once all ingredients and equipment exist, write the recipe file to `recipes/<category>/<recipe-slug>.cook`.
* Adhere to Cooklang syntax:
  * Ingredients: `@ingredient-id{quantity%unit}` (slug must match `id` in `data/ingredients/`)
  * Cookware: `#equipment-id` (must match canonical equipment or alias from `data/equipment.yaml`)
  * Timers: `~timer-name{quantity%unit}`
* Include YAML frontmatter specifying `id`, `title`, `category`, `yield`, `storage`, and `equipment`.
* **Macro Alignment Audit:** Provide the user with the per-portion macro breakdown, compare it against category peers (falling back to `Meal Prep Recipe Book.md` if no local recipes exist yet), flag any significant outliers with suggested adjustments, and present the recipe for user review.

### Phase 4: Verification & Test Execution
* Always run the test suite to ensure data integrity:
  ```bash
  PYTHONPATH=src pytest tests/
  ```
* Ensure that:
  1. All ingredient references in the recipe resolve to canonical entries in `data/ingredients/`.
  2. All units are recognized by `data/units.yaml`.
  3. All equipment tokens match `data/equipment.yaml`.
  4. All Pydantic models validate with zero errors.
* Generate recipe cards when needed or requested:
  ```bash
  PYTHONPATH=src python3 -c 'from meal_prep.renderer import render_all_recipe_cards; render_all_recipe_cards()'
  ```
  Rendered HTML cards are stored in `recipe_cards/` (git-ignored).

---

## 3. Human-in-the-Loop Safeguards

1. **One Step at a Time:** Never rush ahead to generate multiple recipes or bulk edits without intermediate user review.
2. **Deterministic & Auditable:** All calculations (macros per serving, batch costs) must be deterministically derivable from `data/ingredients/` and `data/units.yaml`.
3. **Respect Established Guidelines:** Consult `INGREDIENTS.md` whenever authoring or modifying ingredient staples.
