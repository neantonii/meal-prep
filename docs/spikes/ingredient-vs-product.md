# Spike: ingredient vs. store product

Status: open question, nothing decided. No code changes come with this note.

## Question

Today one ingredient entry is also exactly one store product. Should a
generic ingredient ("2% milk") be separate from the products that can fill it
(Natrel 4 L, a store brand 2 L, ...)?

Decision so far: ingredient = product for now; separating them is postponed.

## What exists today

One entry in `data/ingredients/<aisle>.yaml` mixes both:

| Field | Generic ingredient | Specific product |
|---|---|---|
| `id`, `name`, `step_name` | ✓ | |
| `aisle` | ✓ | |
| `reference.brand`, `reference.product`, `reference.price` | | ✓ |
| `package → <unit>` conversion (package size) | | ✓ |
| `macros` (copied from the label) | mostly | label differs by brand |
| `shelf_life_days`, `storage` | mostly | can differ (UHT vs fresh) |
| other conversions (cup → g, piece → g) | ✓ | |

Recipes reference the ingredient `id`. Brand and product are only shown on
ingredient cards (`ingredient_cards.py`); cost uses price ÷ package size.

## Why it might matter

- **Price changes or a different store** mean editing the ingredient, which
  silently changes every past cost (frozen history, #107).
- **Package size** decides leftovers and shopping lists (inventory spike).
- **Swapping brands** means rewriting macros the recipes depend on.

## Options

| | Model | For | Against |
|---|---|---|---|
| A | **Status quo.** One entry = one product; switching brands edits the entry. | Simplest. Nothing to migrate. | No history of products or prices. |
| B | **Products under an ingredient.** An ingredient lists one or more products (brand, package, price, optional macros override); one is the default. | Recipes unchanged. Prices per product. | Which product a cost uses must be chosen somewhere. |
| C | **Separate product catalog.** Products in their own files, pointing at an ingredient id. | Clean split; a product can carry a price history. | Two catalogs to keep consistent; more files. |
| D | **Price history only.** Keep one product per ingredient but record dated prices. | Fixes the history problem without a new concept. | Doesn't help with brand or package swaps. |

## Open questions

1. **What changes in practice?** Brands, stores, package sizes, or just
   prices? This decides between D and B/C.
2. **Whose macros?** Generic (e.g. USDA) on the ingredient, or each product's
   label?
3. **Which product does a cost use?** A default, the cheapest, or the one
   actually bought (needs purchase records, see the inventory spike)?
4. **Does the diary need to know the product?** Only if cost history must say
   what was actually bought.
5. **Order with #107:** does frozen history land first (snapshotting costs),
   making this less urgent?

## Smallest useful step, whatever the answer

Nothing yet. If #107 snapshots cost and macros into each diary week, price
and brand changes stop rewriting history, and the main pressure for this
split goes away. Revisit when shopping lists or inventory need package
choices.
