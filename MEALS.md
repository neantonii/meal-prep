# Modular Meal & Recipe Authoring Specification (`MEALS.md`)

This document defines the architecture, data schemas, validation protocols, and authoring guidelines for recipes in the meal prep system.

---

## 1. Modular Architecture Overview

All meals in this system are authored as **modular, batch-cooked building blocks**. 

* Every recipe is stored as an independent Cooklang file (`.cook`) with YAML frontmatter.
* Stored strictly under `recipes/<category>/<recipe-slug>.cook`.
* **Zero Inventions / Calculations in Files:** Recipe files contain **only raw quantities, equipment, timers, and storage metadata**. Macro totals, per-serving macros, moisture loss, and batch costs are **deterministically calculated in Python** using `data/ingredients/` and `data/units.yaml`.
* *(Note: Composite meals—fixed assemblies of multiple modular components—will be introduced as a layer on top of these modular building blocks).*

---

## 2. Standard Recipe Categories

Every recipe must specify one of the five validated categories from `src/meal_prep/models/enums.py`:

| Category Slug | Display Name | Scope & Purpose | Directory Destination |
| :--- | :--- | :--- | :--- |
| **`modular_protein`** | Modular Protein | Core batch proteins (chicken, turkey, beef, fish, shrimp, tofu) | `recipes/modular_protein/` |
| **`modular_carb`** | Modular Side (Carbs) | Starchy sides (rice, buckwheat, potatoes, pasta, noodles) | `recipes/modular_carb/` |
| **`modular_cooked_veg`** | Modular Side (Cooked Veg) | Hot cooked vegetables (green beans, cauliflower, corn & peas) | `recipes/modular_cooked_veg/` |
| **`fresh_salad_veg`** | Fresh Vegetables & Salads | Raw crunchy salads and fresh veg (vitaminka, cucumber-tomato) | `recipes/fresh_salad_veg/` |
| **`breakfast`** | Breakfast | Morning meal building blocks (oatmeal, eggs, toast) | `recipes/breakfast/` |

---

## 3. Recipe File Structure (`.cook`)

Each recipe file contains two distinct sections:
1. **YAML Frontmatter:** Structured metadata between triple-dashes `---`.
2. **Cooklang Body:** Standard Cooklang markup with instructions, inline ingredients, cookware, and timers.

### Reference Example: `recipes/modular_protein/air-fried-chicken-breast.cook`

```cooklang
---
id: air-fried-chicken-breast
title: Air-Fried Seasoned Chicken Breast
category: modular_protein

yield:
  servings: 4
  cooked_g: 660

storage:
  fridge_days: 4
  freezer_friendly: true

equipment:
  - air-fryer
  - meat-thermometer
---

Trim any excess fat or tenderloin tendon from @boneless-chicken-breast{4%piece}. Pat thoroughly dry on all sides using paper towels to remove surface purge so the seasoning adheres evenly.

Rub the chicken breasts evenly with @olive-oil{1%tbsp}, then coat all sides with @kosher-salt{1%tsp}, @black-pepper{0.5%tsp}, @garlic-powder{1%tsp}, and @smoked-paprika{1%tsp}.

Preheat #air-fryer to 195°C (380°F). Place breasts in the basket in a single layer with space between them to allow 360-degree air circulation. Cook for ~air-fry-time{16%min}, flipping at the 9-minute mark, until the internal temperature reaches 71°C to 74°C (160°F–165°F) at the thickest part checked with a #meat-thermometer.

Let the chicken rest undisturbed for ~rest-time{5%min} so carryover heat completes cooking and juices redistribute into the meat fibers. Distribute whole breasts (or slice into thick medallions, ~165 g each) into 4 separate meal prep containers, drizzling any rested juices from the board over the portions.
```

---

## 4. Specification Schema

### Frontmatter Schema

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| **`id`** | string | Yes | Lowercase alphanumeric slug with hyphens matching file stem (e.g. `air-fried-chicken-breast`). |
| **`title`** | string | Yes | Human-readable recipe title. |
| **`category`** | enum | Yes | Must match one of the 5 `RecipeCategory` values. |
| **`yield.servings`** | int / float | Yes | Number of batch portions produced (e.g. `4`). |
| **`yield.cooked_g`** | float | Yes | Total cooked batch weight in grams (portion grams = `cooked_g / servings`). |
| **`storage.fridge_days`** | int | Yes | Maximum safe refrigerated shelf life in days. |
| **`storage.freezer_friendly`** | bool | Yes | Whether the cooked dish can be frozen. |
| **`equipment`** | list[str] | Yes | List of equipment IDs from `data/equipment.yaml`. |

---

### Cooklang Body Syntax

* **Ingredients: `@ingredient-id{quantity%unit}`**
  * `@ingredient-id` **must strictly match an existing `id`** in `data/ingredients/<aisle>.yaml`.
  * `quantity`: Numeric float or integer (e.g. `4`, `1.5`, `250`).
  * `unit`: Must be convertible to grams `g` via the ingredient's precomputed `ConversionGraph`.
  * Examples: `@boneless-chicken-breast{4%piece}`, `@olive-oil{15%ml}`, `@kosher-salt{1%tsp}`.

* **Cookware: `#equipment-id`**
  * Must match an equipment item or alias registered in `data/equipment.yaml`.
  * Examples: `#air-fryer`, `#meat-thermometer`, `#skillet`, `#spatula`.

* **Timers: `~timer-name{duration%unit}`**
  * `duration`: Numeric float or integer.
  * `unit`: Must be a valid time unit registered in `data/units.yaml`:
    * Seconds: `s`, `sec`, `second`, `seconds`
    * Minutes: `min`, `mins`, `minute`, `minutes`
    * Hours: `hr`, `hrs`, `hour`, `hours`
  * Examples: `~air-fry-time{16%min}`, `~rest-time{5%min}`, `~surface-drying{1%hr}`.

---

## 5. Values Derived Automatically by Python

The recipe file never stores redundant or computed values. When a recipe is loaded, Python derives:

* **Portion weight:** `yield.cooked_g / yield.servings`
* **Raw batch weight:** Sum of all ingredient grams
* **Moisture / cooking yield loss %:** `1 - (yield.cooked_g / raw_batch_weight_g)`
* **Macros per batch & per serving:** Calories, protein, fat, carbs, fiber, sodium, potassium
* **Batch cost & cost per serving:** Retail cost based on ingredient reference prices
* **Safe fridge storage window:** $\min(\text{storage.fridge\_days}, \min(\text{ingredient shelf life}))$

---

## 6. Step-by-Step Recipe Authoring Workflow

When adding a new recipe (human or AI agent), follow this strict 4-step workflow:

### Step 1: Pre-requisite Ingredient Audit
1. Inspect the original recipe and list ALL ingredients needed (proteins, produce, dairy, oils, and minor spices/seasonings).
2. Cross-reference each ingredient against `data/ingredients/`.
3. **If ANY ingredient is missing: STOP IMMEDIATELY.**
   * Do NOT invent, assume, or silently add placeholder ingredients to unblock recipe compilation or pass tests.
   * Every ingredient must be explicitly confirmed/opted in by the user with real purchase details (brand, package size, price).
   * Run USDA FoodData Central cross-validation behind the scenes (filling in omitted micronutrients only after the reference product is confirmed).
   * Add the ingredient entry to `data/ingredients/<aisle>.yaml` only after user confirmation.

### Step 2: Equipment Audit
1. Ensure all kitchen tools mentioned exist in `data/equipment.yaml`.
2. If a new specialized tool is needed (e.g. `pasta-roller`, `sous-vide`), add it to `data/equipment.yaml` with appropriate categories and temperature limits.

### Step 3: Author the `.cook` Recipe File
1. Create `recipes/<category>/<slug>.cook`.
2. Add complete YAML frontmatter (slug, title, category, yield, storage, equipment).
3. Write clear, sequential cooking instructions using `@ingredient{qty%unit}`, `#equipment`, and `~timer{duration%unit}`.

### Step 4: Macro Alignment & Category Comparative Audit
Before finalizing the recipe, compute and present the per-portion macro breakdown to the user and perform a comparative analysis against the recipe's category standards:

1. **Per-Portion Macro Analysis:**
   * **Primary Focus:** Calories and Protein (ensure target protein density is achieved).
   * **Secondary Focus:** Carbohydrates and Total Fat.
   * **Tertiary Focus:** Dietary Fiber, Sodium, and Potassium.
2. **Category Comparative Benchmarks:**
   * **`modular_protein`:** Typically 35–55 g protein, 250–420 kcal per serving.
   * **`modular_carb`:** Typically 35–50 g carbs, 3–6 g fiber, 180–260 kcal per serving.
   * **`modular_cooked_veg`:** Typically 40–100 kcal, 3–6 g fiber per serving.
   * **`fresh_salad_veg`:** Typically 30–90 kcal, high volume, light healthy fats.
   * **`breakfast`:** Typically 30–45 g protein, balanced carbs & fats.
3. **Outlier Detection & Decision Protocol:**
   * Compare against other recipes in the same category directory (`recipes/<category>/`).
   * **Cold-Start Fallback Rule:** If no other recipes exist in `recipes/<category>/` yet (e.g. during initial system bootstrap or migration), **fall back to the reference recipes in `Meal Prep Recipe Book.md`** under the corresponding category to construct the comparative benchmark table.
   * If the proposed recipe is a significant outlier (e.g., protein density is too low, portion weight is disproportionately large/small, or fat/calories deviate heavily from category peers), **explicitly alert the user, provide a clear comparison table, and suggest adjustments** (e.g. adjusting batch size, serving count, or oil amount).
   * The human user always makes the final decision.

### Step 5: Automated Verification & Test Execution
Run the automated validation suite:
```bash
PYTHONPATH=src pytest tests/
```
The test suite ensures:
* YAML frontmatter validates against `schemas/recipe_frontmatter.schema.json` and Pydantic models.
* Every `@ingredient` resolves to an existing ingredient file in `data/ingredients/`.
* Every unit converts cleanly to grams through the conversion graph.
* Every `#equipment` is registered in `data/equipment.yaml`.
* All timers use registered time units (`s`, `min`, `hr`).

### Step 6: HTML Recipe Card Generation
To generate visual, interactive recipe cards mirroring the `recipes/` directory structure:
```bash
PYTHONPATH=src python3 -c 'from meal_prep.renderer import render_all_recipe_cards; render_all_recipe_cards()'
```
Output is stored in `recipe_cards/<category>/<recipe-id>.html` (git-ignored).
Recipe cards include:
* Macro banner (Calories, Protein, Fat, Sat Fat, Carbs, Fiber, Sugars, Sodium, Potassium) dynamically omitting zero-value sub-nutrients.
* Interactive ingredient checklist with calculated batch weights, retail costs, and kcal contributions.
* Equipment badges and safe storage guidelines.
* Numbered instructions with Cooklang pill badges for ingredients, cookware, and timers.

