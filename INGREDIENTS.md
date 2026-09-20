# INGREDIENTS.md — Ingredient Authoring Guidelines

This guide defines the standards for all ingredient entries across the 7 aisle files in `data/ingredients/<aisle>.yaml`.

---

## ⚠️ Critical Rule: No Guessed Data & Mandatory Cross-Validation

1. **NEVER invent, estimate, or assume ingredient data** (macros, prices, package weights, or product names).
2. **Always prompt the user to provide the exact reference details** from their real purchase:
   * Benchmark product (store/brand, exact product name, price in CAD).
   * Package size and mass (e.g. 950 g pack, 454 g bag).
   * Label nutrition facts (calories, protein, fat, saturated fat, carbs, fiber, sugars, sodium_mg, potassium_mg).
   * Unit-to-gram conversions (e.g. 1 item = X grams, 1 cup = X grams).

3. **Mandatory Cross-Registry Verification (USDA FoodData Central):**
   * **Always cross-check supplied values against the USDA FoodData Central registry** (Foundation / SR Legacy databases).
   * **Be suspicious of missing or zero values:**
     * Validate whether a zero makes biological sense (e.g. 0 g carbs/fiber/sugars is natural for raw chicken breast, but 0 mg potassium or sodium is suspicious).
     * If a value is missing on the product label (e.g. label omits potassium or saturated fat), check USDA and inform the user.
   * **Alert only on discrepancies:** If data aligns with USDA, simply report that validation passed. Do not spam full tables. Only alert the user if a field is suspicious, missing, or deviates by >15%.

---

## Ingredient Schema Specification & JSON Schema

All ingredient files are validated against the formal JSON Schema located at **`schemas/ingredients.schema.json`** (auto-generated from the Pydantic models). 

In any IDE (VS Code, Cursor, IntelliJ), referencing this schema at the top of the YAML file provides instant autocompletion, hover documentation, and syntax error detection:

```yaml
# yaml-language-server: $schema=../../schemas/ingredients.schema.json
```

### Fully Commented Reference Example

```yaml
# yaml-language-server: $schema=../../schemas/ingredients.schema.json

- id: boneless-chicken-breast                   # Canonical slug (lowercase alphanumeric with hyphens)
  name: Boneless, Skinless Chicken Breast       # Generic display name (never put brand names here)
  aisle: meat                                   # Must match enclosing filename and data/aisles.yaml
  storage: refrigerated                        # ambient | refrigerated | frozen
  shelf_life_days: 3                            # Mandatory shelf life in days under this storage mode

  package:
    container: pack                             # Packaging noun from data/units.yaml (pack, bag, carton, etc.)
    unit: piece                                 # Discrete item unit or base unit (piece, slice, item, g, ml)
    amount: 4                                   # Quantity of units inside package
    container_weight_g: 950                     # Total net package mass in grams

  reference:
    brand: Compliments                          # Brand or store line
    product: Compliments Chicken Breasts Boneless Skinless Value Pack # Full commercial name
    price: 22.60                                # Retail price in CAD (numeric float)

  macros_per_100g:
    calories_kcal: 110.0                        # Mandatory core macros (per 100g raw/unprepared)
    protein_g: 23.0                             # All macronutrient field names include explicit units
    fat_g: 2.5
    carbs_g: 0.0
    fiber_g: 0.0
    # Optional extended nutrients (names include units):
    saturated_fat_g: 0.5
    sugars_g: 0.0
    sodium_mg: 45.0
    potassium_mg: 350.0

  conversions:
    - unit: piece                               # Mandatory list of unit-to-gram conversion factors
      g: 237.5                                  # 1 piece = 237.5 g (950g / 4 pieces)
```

---

## Field Definitions

### 1. `id` (string, required)
* Lowercase alphanumeric with hyphens only (e.g. `boneless-chicken-breast`, `basmati-rice`).
* Must be unique across all 7 aisle files.

### 2. `name` (string, required)
* Canonical generic staple name (e.g. `"Boneless, Skinless Chicken Breast"`).
* **Never include brand names in `name`** (brand names belong inside `reference.brand`).

### 3. `aisle` (string, required)
* Must match one of the 7 valid aisles in `data/aisles.yaml` (`produce`, `bakery`, `meat`, `seafood`, `dairy`, `pantry`, `spices`).
* Must match the enclosing file name (e.g. `meat.yaml`).

### 4. `storage` (enum string, required)
Must be one of the three validated storage types from `src/meal_prep/models/enums.py`:
* `ambient`: Room temperature dry pantry goods, oils, whole potatoes/onions.
* `refrigerated`: Chilled items with short/medium shelf lives (fresh chicken, dairy, salad greens).
* `frozen`: Frozen items stored long-term (fish fillets, frozen shrimp, frozen peas/berries).

### 5. `shelf_life_days` (integer, required)
* Freshness shelf-life in days under its designated storage mode. Always mandatory to ensure meal planners can track freshness limits.

### 6. `package` (object, required)
Represents the standard retail container you purchase:
* `container`: Valid container noun from `data/units.yaml` (`pack`, `bag`, `carton`, `bottle`, `tub`, `can`, `clamshell`, `loaf`, `bunch`).
* `unit`: Unit noun of the items inside (`piece`, `slice`, `item`, `g`, `ml`).
* `amount`: Numeric count or quantity of units inside the package (e.g. `4` pieces, `12` eggs, `20` slices, `900` g).
* `container_weight_g`: Total net mass of the package in grams (e.g. `950`, `600`, `900`).

### 7. `reference` (object, required)
Benchmark retail pricing and product metadata:
* `brand`: Brand name (e.g. `Compliments`, `Kirkland Signature`, `Selection`).
* `product`: Exact retail brand/product name on receipt or packaging.
* `price`: Benchmark purchase price in CAD (numeric float).
*(Note: `price_per_100g`, `price_per_kg`, and `price_per_unit` are dynamically computed properties in Python; do NOT hardcode them in YAML).*

### 8. `macros_per_100g` (object, required)
* **Always based on 100 g of raw/unprepared staple**, unless the item is inherently pre-cooked/canned.
* **Core fields (mandatory):**
  * `calories_kcal`: kcal (float)
  * `protein_g`: grams (float)
  * `fat_g`: grams (float)
  * `carbs_g`: grams (float)
  * `fiber_g`: grams (float)
* **Optional detailed fields:**
  * `saturated_fat_g`: grams (float)
  * `sugars_g`: grams (float)
  * `sodium_mg`: milligrams (float)
  * `potassium_mg`: milligrams (float)

### 9. `conversions` (list of objects, required)
* Mandatory list of unit-to-gram conversion factors.
* Any discrete or volume measurement unit used in recipes (e.g. `piece`, `cup`, `tbsp`, `slice`, `clove`) **must** be defined with an explicit `g` conversion factor (grams).
* For staples measured primarily by weight (e.g. rice, salt), provide the standard kitchen volumetric conversions (e.g. `cup`, `tbsp`).
* Example:
  ```yaml
  conversions:
    - unit: piece
      g: 237.5
  ```

---

## Aisle File Destination

Ingredients are strictly partitioned into one of the 7 files in `data/ingredients/`:

| Aisle File | What Belongs Inside |
| :--- | :--- |
| `data/ingredients/produce.yaml` | Vegetables, fruits, fresh herbs, potatoes, onions, garlic (fresh and frozen) |
| `data/ingredients/bakery.yaml` | Whole grain bread, tortillas, pita, wraps |
| `data/ingredients/meat.yaml` | Chicken, beef, turkey, pork (fresh and frozen) |
| `data/ingredients/seafood.yaml` | Trout, salmon, pollock, shrimp (fresh and frozen) |
| `data/ingredients/dairy.yaml` | Eggs, milk, yogurt, cheeses, butter |
| `data/ingredients/pantry.yaml` | Grains (rice, buckwheat, oats), pasta, oils, vinegars, canned goods, chocolate |
| `data/ingredients/spices.yaml` | Salt, pepper, paprika, garlic powder, dried herbs, seasoning blends |

---

## Pre-Commit Verification Checklist

Before saving any new or updated ingredient:
1. Did the user provide or approve the reference product, price, and nutrition facts?
2. Is the `id` unique across all aisles?
3. Is `storage` set to `ambient`, `refrigerated`, or `frozen`?
4. Is `package.name` one of the approved packaging nouns?
5. Do non-gram units have explicit `conversions` to grams?
6. Does `PYTHONPATH=src pytest tests/` pass with zero errors?
