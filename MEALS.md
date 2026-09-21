# Modular Meal & Recipe Specification (`MEALS.md`)

This document defines the architecture, data schemas, validation rules, and category benchmarks for recipes in the meal prep system.

---

## 1. Modular Architecture Overview

All meals in this system are authored as **modular, batch-cooked building blocks**.

* **Independent Cooklang Files:** Every recipe is stored as an isolated Cooklang file (`.cook`) with YAML frontmatter.
* **Category Partitioning:** Stored strictly under `recipes/<category>/<recipe-slug>.cook`.
* **Zero Redundant / Computed Data in Files:** Recipe files contain **only raw quantities, equipment, timers, and storage metadata**. Macro totals, per-serving macros, moisture loss, and batch costs are **deterministically calculated in Python** using `data/ingredients/` and `data/units.yaml`.
* **Composite Meals:** High-level assemblies (e.g. modular protein + carb + cooked veg) sit as a composition layer on top of these modular building blocks.

---

## 2. Standard Recipe Categories

Every recipe must specify one of the five validated categories from `src/meal_prep/models/enums.py`:

| Category Slug | Display Name | Scope & Purpose | Directory Destination | Category Macro Benchmarks |
| :--- | :--- | :--- | :--- | :--- |
| **`modular_protein`** | Modular Protein | Core batch proteins (chicken, turkey, beef, fish, shrimp, tofu) | `recipes/modular_protein/` | 35-55 g protein, 250-420 kcal |
| **`modular_carb`** | Modular Side (Carbs) | Starchy sides (rice, buckwheat, potatoes, pasta, noodles) | `recipes/modular_carb/` | 35-50 g carbs, 3-6 g fiber, 180-260 kcal |
| **`modular_cooked_veg`** | Modular Side (Cooked Veg) | Hot cooked vegetables (green beans, cauliflower, corn & peas) | `recipes/modular_cooked_veg/` | 40-100 kcal, 3-6 g fiber |
| **`fresh_salad_veg`** | Fresh Vegetables & Salads | Raw crunchy salads and fresh veg (vitaminka, cucumber-tomato) | `recipes/fresh_salad_veg/` | 30-90 kcal, high volume, light healthy fats |
| **`breakfast`** | Breakfast | Morning meal building blocks (oatmeal, eggs, toast) | `recipes/breakfast/` | 30-45 g protein, balanced carbs & fats |

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
| **`id`** | string | Yes | Lowercase alphanumeric slug with hyphens matching file stem (e.g. `boiled-basmati-rice`). |
| **`title`** | string | Yes | Human-readable recipe title. |
| **`category`** | enum | Yes | Must match one of the 5 `RecipeCategory` values. |
| **`yield.servings`** | int / float | Yes | Number of batch portions produced (e.g. `1` or `4`). |
| **`yield.cooked_g`** | float | Yes | Total finished cooked batch weight in grams (portion grams = `cooked_g / servings`). |
| **`storage.fridge_days`** | int | Yes | Maximum safe refrigerated shelf life in days. |
| **`storage.freezer_friendly`** | bool | Yes | Whether the cooked dish can be safely frozen. |
| **`equipment`** | list[str] | Yes | List of equipment IDs matching canonical items or aliases in `data/equipment.yaml`. |

### Cooklang Body Syntax

* **Ingredients: `@ingredient-id{quantity%unit}`**
  * `@ingredient-id` **must strictly match an existing `id`** in `data/ingredients/<aisle>.yaml`.
  * `quantity`: Numeric float or integer (e.g. `4`, `1.5`, `250`, `0.33`).
  * `unit`: Must be convertible to grams `g` via the ingredient precomputed `ConversionGraph` or universal units in `data/units.yaml`.
  * Examples: `@boneless-chicken-breast{4%piece}`, `@olive-oil{1%tbsp}`, `@kosher-salt{0.25%tsp}`, `@basmati-rice{0.33%cup}`.

* **Cookware: `#equipment-id`**
  * Must match an equipment item or alias registered in `data/equipment.yaml`.
  * Examples: `#air-fryer`, `#meat-thermometer`, `#saucepan`, `#skillet`.

* **Timers: `~timer-name{duration%unit}`**
  * `duration`: Numeric float or integer.
  * `unit`: Must be a valid time unit registered in `data/units.yaml`:
    * Seconds: `s`, `sec`, `second`, `seconds`
    * Minutes: `min`, `mins`, `minute`, `minutes`
    * Hours: `hr`, `hrs`, `hour`, `hours`
  * Examples: `~air-fry-time{16%min}`, `~simmer-time{11%min}`, `~steam-time{5%min}`.

### Untracked Ingredients Policy (Water)
* **Water is strictly untracked as an ingredient token:** Do NOT tag water as an ingredient (e.g. do not write `@water{120%ml}`). Water carries zero macros and negligible cost; adding dummy water catalog entries pollutes inventory tracking.
* **Explicit Cooking Volume Required:** While untracked as a token, the exact liquid volume for boiling, steaming, or simmering must be explicitly stated in the instruction text (e.g. *"In a #saucepan, combine the rinsed rice, 120 ml (1/2 cup) cold water, and..."*).

### Measurement Units & Culinary Usability
Review the chosen measurement units in the recipe body to ensure they reflect intuitive home cooking:
* **Small fats, dairy, condiments:** Prefer volumetric spoons (`1 tsp`, `1 tbsp`) over awkward scale grams (`4.7 g`, `5 g`).
* **Dry grains & starches:** Prefer standard cups or spoons (`0.33 cup`, `0.5 cup`) over awkward scale numbers like `63 g`.
* **Spices & seasonings:** Prefer `0.25 tsp`, `0.5 tsp`, `1 tsp` over fractional grams (`1.1 g`, `2.3 g`).
* **Bulk proteins & large produce:** Grams `g` (`450 g`, `200 g`) or discrete counts (`piece`, `clove`) remain the preferred standard.
* **Conversion Graph Integrity:** Ensure every chosen culinary unit (`tsp`, `tbsp`, `cup`, `piece`) is supported by the ingredient's precomputed `ConversionGraph` to grams.

---

## 5. Values Derived Automatically by Python

The recipe file never stores redundant or computed values. When a recipe is loaded, Python deterministically derives:

* **Portion weight:** `yield.cooked_g / yield.servings`
* **Raw batch weight:** Sum of all ingredient grams
* **Moisture / cooking yield loss %:** `1 - (yield.cooked_g / raw_batch_weight_g)` (negative indicates water absorption, e.g. for grains/pasta)
* **Macros per batch & per serving:** Calories, protein, fat, saturated fat, carbohydrates, fiber, sugars, sodium, potassium
* **Batch cost & cost per serving:** Retail cost derived from ingredient reference package pricing
* **Safe fridge storage window:** min(storage.fridge_days, min(ingredient shelf life))

---

## 6. Validation, Math Auditing & Tooling

### Automated Test Suite
Run the test suite to verify frontmatter schemas, ingredient references, unit conversions, and cookware:
```bash
PYTHONPATH=src python3 -m pytest tests/
```

### Reviewing Math & Macros via Library / CLI
Inspect batch totals, cooking loss, portion scale weight, macros, and cost breakdown:
```bash
PYTHONPATH=src python3 -c 'from meal_prep.library import MealPrepLibrary; print(MealPrepLibrary.load().review_math("<recipe-slug>"))'
```
Or via the CLI:
```bash
PYTHONPATH=src python3 -m meal_prep.cli audit <category> <recipe-slug>
```

### HTML Recipe Card Generation
Generate standalone visual recipe cards:
```bash
PYTHONPATH=src python3 -c 'from meal_prep.renderer import render_all_recipe_cards; render_all_recipe_cards()'
```
Output files are placed in `recipe_cards/<category>/<recipe-slug>.html`.

---

## 7. Interactive Authoring Workflow & Skill

For the interactive AI agent workflow, step-by-step authoring sequence, and guardrails (mandatory user opt-in, zero guesswork, USDA cross-checks, and file-touch boundaries), refer to the **`meal-authoring` skill** (`.agents/skills/meal-authoring/SKILL.md`).
