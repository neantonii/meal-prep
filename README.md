# Meal Prep

An intelligent meal prep data normalization, indexing, and meal planning system built in Python.

## Overview

The core goal of this project is to take structured, batch-cooked recipes from our markdown recipe book and transform them into a fully normalized, queryable, and automated meal planning engine.

### Project Roadmap & Core Pillars

1. **Data Normalization:**
   * Parse and extract structured data from `Meal Prep Recipe Book.md` into normalized data models (recipes, ingredients, macronutrients, unit pricing, aisle taxonomy, and preparation metadata).
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

## Repository Starting Point

* **`Meal Prep Recipe Book.md`**: The foundation document containing 22 modular batch-cooked recipes, standardized grocery aisle taxonomy, and ingredient price references.

