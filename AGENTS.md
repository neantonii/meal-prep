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
* **CRITICAL RULE: NO SILENT INGREDIENT CREATION (ZERO GUESSWORK)**
  * **The agent must NEVER silently create, assume, or add ingredients to `data/ingredients/` without user opt-in.** This applies equally to primary proteins, cooking fats, produce, sauces, and small spice staples (e.g. onion powder, dried herbs).
  * **Strict Stop on Missing Items:** If any ingredient is missing from `data/ingredients/`, the agent must halt and ask the user for their real purchase details. Never create an assumed product/price entry just to make the `.cook` parser pass or satisfy a test.
  * **User Opt-In Required:** An ingredient may only be added to `data/ingredients/` after the user has explicitly provided or approved the specific reference item (store, brand, package size, price).
  * **Behind-the-Scenes USDA Cross-Validation (Nutrient Verification Only):**
    * Once the user provides the product reference, cross-check its nutritional profile against USDA FoodData Central silently behind the scenes.
    * Use USDA data to fill in omitted label micronutrients (potassium, sodium, saturated fat) when the user directs to use USDA or when labels omit them.
    * Only alert the user if a label value deviates significantly (>15%) from USDA biological norms.
* Follow the authoring guidelines in `INGREDIENTS.md`.
* Present a concise summary of the added/updated ingredient to the user.

### Phase 3: Recipe File Authoring
* Follow the authoring guidelines in `MEALS.md`.
* Once all ingredients and equipment exist, write the recipe file to `recipes/<category>/<recipe-slug>.cook`.
* Adhere to Cooklang syntax:
  * Ingredients: `@ingredient-id{quantity%unit}` (slug must match `id` in `data/ingredients/`)
  * Cookware: `#equipment-id` (must match canonical equipment or alias from `data/equipment.yaml`)
  * Timers: `~timer-name{quantity%unit}`
* Include YAML frontmatter specifying `id`, `title`, `category`, `yield`, `storage`, and `equipment`.
* **Macro Alignment Audit:** Provide the user with the per-portion macro breakdown, compare it against category peers, flag any significant outliers with suggested adjustments, and present the recipe for user review.
* Audit the math using the calculator (do not read the renderer):
  ```bash
  PYTHONPATH=src python3 -c 'from meal_prep.library import MealPrepLibrary; print(MealPrepLibrary.load().review_math("<recipe-slug>"))'
  ```

### Phase 4: Verification & Test Execution
* Always run the test suite to ensure data integrity:
  ```bash
  PYTHONPATH=src python3 -m pytest tests/
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

## 3. Human-in-the-Loop Safeguards & Agent File-Touch Boundaries

1. **One Step at a Time:** Never rush ahead to generate multiple recipes or bulk edits without intermediate user review.
2. **Deterministic & Auditable:** All calculations (macros per serving, batch costs) must be deterministically derivable from `data/ingredients/` and `data/units.yaml`.
3. **Commit & Amend Policy:** When importing meals from the recipe book, keep changes in the working directory while drafting and refining. Amend/commit ONLY AFTER the user gives explicit final approval on the imported meal.
4. **Respect Established Guidelines:** Consult `INGREDIENTS.md` whenever authoring or modifying ingredient staples.
5. **Zero Silent Additions:** The agent is strictly forbidden from adding unconfirmed ingredients, equipment, or recipes behind the scenes. Missing ingredients are a mandatory hard stop to request the user's reference product or confirm existing book data before authoring recipes.
6. **Strict File Scope & Anti-Browsing Directive (Anti-Hallucination & Token Hygiene):**
   * **Allowed Files:** The agent must ONLY touch the target `recipes/<category>/<recipe-slug>.cook`, the specific ingredient file being modified (`data/ingredients/<aisle>.yaml`), and read-only references `data/equipment.yaml` / `data/units.yaml`.
   * **FORBIDDEN:** NEVER load or browse `src/meal_prep/renderer.py` (it is a ~23 KiB HTML/CSS template; loading it burns context tokens and it contains no meal math). NEVER browse `src/meal_prep/models/*.py`, `tests/*.py`, or unrelated aisle files. Use `MealPrepLibrary.load().review_math("<slug>")` for math inspection.
