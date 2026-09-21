# Ingredient Catalog Specification (`INGREDIENTS.md`)

This document defines the architecture, data schemas, validation protocols, and authoring standards for ingredients across the 7 aisle files in `data/ingredients/<aisle>.yaml`.

---

## 1. Catalog Architecture Overview

The ingredient catalog serves as the single source of truth for all pricing, nutritional data, and unit conversion factors in the meal prep system.

* **File-Based Partitioning:** Divided across 7 grocery store aisle files in `data/ingredients/<aisle>.yaml`.
* **Canonical Identifiers:** Every ingredient has a unique lowercase hyphenated `id` (e.g. `boneless-chicken-breast`, `basmati-rice`).
* **Deterministic Calculations:** Retail unit prices, cost per 100g/kg, and macro scaling are derived deterministically in Python using `src/meal_prep/calculator.py`.
* **Schema Validation:** Every ingredient file is validated against the formal JSON Schema in `schemas/ingredients.schema.json` and strict Pydantic v2 models in `src/meal_prep/models/ingredient.py`.

---

## 2. Aisle Taxonomy & File Destinations

Ingredients are strictly partitioned by their physical grocery aisle into one of the 7 YAML files:

| Aisle Slug | Aisle Name | File Path | Scope & Typical Items |
| :--- | :--- | :--- | :--- |
| **`produce`** | Produce | `data/ingredients/produce.yaml` | Fresh and frozen vegetables, fresh herbs, fruits, onions, garlic, potatoes |
| **`bakery`** | Bakery | `data/ingredients/bakery.yaml` | Breads, tortillas, pita, sandwich buns, wraps |
| **`meat`** | Meat | `data/ingredients/meat.yaml` | Fresh and frozen poultry, beef, pork, turkey |
| **`seafood`** | Seafood | `data/ingredients/seafood.yaml` | Fresh and frozen fish fillets, salmon, trout, shrimp |
| **`dairy`** | Dairy & Refrigerated | `data/ingredients/dairy.yaml` | Eggs, milk, yogurt, cottage cheese, cheese, butter |
| **`pantry`** | Pantry | `data/ingredients/pantry.yaml` | Dry grains (rice, buckwheat, oats), pasta, oils, vinegars, canned goods |
| **`spices`** | Spices & Seasonings | `data/ingredients/spices.yaml` | Salt, pepper, paprika, garlic powder, dried herbs, spice blends |

*Rule:* The `aisle` field of every ingredient inside a file must match the enclosing filename and `data/aisles.yaml`.

---

## 3. Reference Example

```yaml
# yaml-language-server: $schema=../../schemas/ingredients.schema.json

- id: boneless-chicken-breast
  name: Boneless, Skinless Chicken Breast
  aisle: meat
  storage: refrigerated
  shelf_life_days: 3

  package:
    container: pack
    unit: piece
    amount: 4
    container_weight_g: 950

  reference:
    brand: Compliments
    product: Compliments Chicken Breasts Boneless Skinless Value Pack
    price: 22.60

  macros_per_100g:
    calories_kcal: 110.0
    protein_g: 23.0
    fat_g: 2.5
    carbs_g: 0.0
    fiber_g: 0.0
    saturated_fat_g: 0.5
    sugars_g: 0.0
    sodium_mg: 45.0
    potassium_mg: 350.0

  conversions:
    - from: piece
      to: g
      factor: 237.5
```

---

## 4. Specification Schema

### Top-Level Fields

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| **`id`** | string | Yes | Unique lowercase alphanumeric slug with hyphens (e.g. `roasted-buckwheat`). |
| **`name`** | string | Yes | Generic culinary display name without brand names (e.g. `Roasted Buckwheat Groats`). |
| **`aisle`** | enum | Yes | Must match one of the 7 valid aisles and the enclosing filename. |
| **`storage`** | enum | Yes | Valid storage mode: `ambient`, `refrigerated`, or `frozen`. |
| **`shelf_life_days`** | int | Yes | Maximum safe shelf life in days under the designated storage mode. |
| **`package`** | object | Yes | Retail container packaging details (see below). |
| **`reference`** | object | Yes | Commercial retail product and pricing benchmark (see below). |
| **`macros_per_100g`** | object | Yes | Nutritional profile per 100g of raw/unprepared staple (see below). |
| **`conversions`** | list[object] | Yes | List of explicit unit-to-gram conversion edges (see below). |

---

### `package` Schema

Represents the physical retail package purchased at the grocery store:

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| **`container`** | string | Yes | Valid container noun from `data/units.yaml` (`pack`, `bag`, `carton`, `bottle`, `tub`, `can`, `clamshell`, `loaf`, `bunch`). |
| **`unit`** | string | Yes | Unit noun of items inside the package (`piece`, `slice`, `item`, `clove`, `g`, `ml`). |
| **`amount`** | float | Yes | Count or quantity of units inside the package (e.g. `4` pieces, `12` eggs, `908` g). |
| **`container_weight_g`** | float | Yes | Total net weight of the container in grams (e.g. `950`, `454`, `908`). |

---

### `reference` Schema

Benchmark retail purchasing data:

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| **`brand`** | string | Yes | Brand or store line (e.g. `Compliments`, `Kirkland Signature`, `India Gate`). |
| **`product`** | string | Yes | Full commercial product name from store shelf or receipt. |
| **`price`** | float | Yes | Benchmark retail purchase price in CAD (e.g. `17.99`). |

*(Note: `price_per_100g`, `price_per_kg`, and `price_per_unit` are computed dynamically by Python. Do NOT store computed prices in YAML).*

---

### `macros_per_100g` Schema

All macronutrient and micronutrient values are standardized to **100 g of raw, unprepared food**:

| Field | Type | Required | Unit | Description |
| :--- | :--- | :--- | :--- | :--- |
| **`calories_kcal`** | float | Yes | kcal | Total energy per 100 g. |
| **`protein_g`** | float | Yes | g | Total protein in grams. |
| **`fat_g`** | float | Yes | g | Total crude fat in grams. |
| **`carbs_g`** | float | Yes | g | Total carbohydrates in grams. |
| **`fiber_g`** | float | Yes | g | Total dietary fiber in grams. |
| **`saturated_fat_g`** | float | No | g | Saturated fatty acids in grams. |
| **`sugars_g`** | float | No | g | Total sugars in grams. |
| **`sodium_mg`** | float | No | mg | Sodium in milligrams. |
| **`potassium_mg`** | float | No | mg | Potassium in milligrams. |

---

### `conversions` Schema

Directed unit conversion edges bridging non-gram culinary units to grams:

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| **`from`** | string | Yes | Source unit name or alias (e.g. `cup`, `piece`, `tbsp`). |
| **`to`** | string | Yes | Target unit name or alias (typically `g`). |
| **`factor`** | float | Yes | Multiplier such that 1 from = factor * 1 to (e.g. `180.0` for `cup -> g`). |

---

## 5. Conversion Graph Rules & Dimensional Integrity

The system dynamically builds a `ConversionGraph` per ingredient. To ensure mathematical determinism and prevent contradictory conversion paths, the following invariants are strictly enforced:

1. **Automatic Bidirectional Traversal:** Adding an edge `A -> B` with factor $k$ automatically registers the reverse path `B -> A` with factor $1 / k$.
2. **Dimension Uniqueness (At Most One Edge Across Dimension Pairs):**
   * Universal continuous conversions (`mass`, `volume`, `time`) are defined globally in `data/units.yaml`.
   * **Intra-dimension conversions are strictly forbidden:** Do not define `tbsp -> tsp` or `kg -> g` in an ingredient; they are already universal.
   * **Inter-dimension conversions must have at most one edge:** Defining both `tbsp -> g` and `tsp -> g`, or defining `ml -> g` and `g -> tbsp`, creates a double conversion across `{volume, mass}` and is rejected by model validation. Choose ONE canonical volume bridge (e.g. `cup -> g` or `tbsp -> g`).
3. **Discrete Count Bridges:** Discrete units (`clove`, `head`, `piece`, `slice`) represent independent physical items. Multiple discrete units may each define their own bridge to mass (e.g. both `clove -> g` and `head -> g` on `fresh-garlic`).
4. **Self-Conversions Forbidden:** Conversions from a unit to itself (e.g. `piece -> piece`) are invalid.
5. **Container Derived Automatically:** Container nouns (`pack`, `bag`, `carton`) are derived automatically from the `package:` block and must NOT be duplicated in `conversions`.

---

## 6. Values Derived Automatically by Python

When an ingredient is loaded into the `MealPrepLibrary`, Python calculates:

* **Price per 100g:** `(price / container_weight_g) * 100`
* **Price per kg:** `(price / container_weight_g) * 1000`
* **Price per discrete unit:** `price / amount`
* **Shortest Path Conversion:** Using Dijkstra's algorithm over the `ConversionGraph`, Python automatically converts any valid unit (e.g. `tsp`, `tbsp`, `cup`, `piece`) to grams.

---

## 7. Data Quality & Nutritional Standards

### Benchmark Reference Requirements
* **Real Commercial Products Only:** Every ingredient entry must map to an actual, verifiable retail grocery product. Placeholder, generic, or estimated pricing and packaging values are not permitted in the catalog.
* **Mandatory Pricing in CAD:** The `reference.price` must record the verified retail purchase price in Canadian Dollars (CAD) for the specified package size.

### Nutritional Standards & USDA Cross-Validation
* **Raw / Unprepared Baseline:** Macronutrient and energy values (`macros_per_100g`) are standardized to 100 g of the raw, unprepared staple, unless the product is sold inherently pre-cooked or canned (e.g. canned beans, tuna).
* **Cross-Validation with USDA FoodData Central:**
  * Nutritional values from manufacturer packaging must align with biological norms defined in USDA FoodData Central (Foundation Foods or SR Legacy).
  * Where package nutrition labels omit statutory micronutrients (such as sodium, potassium, or saturated fat), USDA standard reference values for the corresponding commodity are used to populate the catalog.
  * Any nutrient value that deviates significantly (>15%) from USDA biological averages requires explicit verification before inclusion.

---

## 8. Validation & Verification Tooling

### IDE Autocompletion & Schema Validation
Add this header to any ingredient file to enable real-time validation in VS Code, Cursor, or IntelliJ:
```yaml
# yaml-language-server: $schema=../../schemas/ingredients.schema.json
```

### Automated Test Suite
Run the test suite to verify ingredient schemas, aisle matching, unique IDs, and conversion graphs:
```bash
PYTHONPATH=src python3 -m pytest tests/test_ingredients.py
```

### Library Catalog Inspection
Verify that all catalog ingredients load cleanly:
```bash
PYTHONPATH=src python3 -c 'from meal_prep.library import MealPrepLibrary; lib = MealPrepLibrary.load(); print(f"Loaded {len(lib.ingredients)} ingredients across {len(lib.aisles)} aisles.")'
```

---

## 9. Interactive Authoring & Agent Playbook

For interactive agent workflows, missing-ingredient prompts, and operational guardrails when adding new ingredients during recipe creation, refer to the **`meal-authoring` skill** (`.agents/skills/meal-authoring/SKILL.md`).
