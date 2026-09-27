"""Recipe Nutrition, Yield, and Cost Calculator.

Provides deterministic mathematical calculations for recipes:
- Multi-hop ingredient conversion to grams
- Ingredient cost and nutrient scaling
- Batch totals (raw weight, cooking loss %, batch cost, batch macros)
- Per-portion values (cooked serving weight, serving cost, serving macros)
- Ingredient-constrained safe storage windows
- Math review and audit formatting
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING
from pydantic import BaseModel
from meal_prep.models.ingredient import MacrosInfo
from meal_prep.services.pricing import price_per_100g

if TYPE_CHECKING:
    from meal_prep.models.recipe import Recipe
    from meal_prep.models.ingredient import Ingredient
    from meal_prep.models.equipment import EquipmentRegistry
    from meal_prep.models.units import UnitsRegistry


@dataclass(frozen=True)
class IngredientBreakdown:
    """Mathematical and nutritional breakdown of a single ingredient in a recipe."""
    id: str
    name: str
    aisle: str
    quantity: float
    unit: str
    grams: float
    cost: float
    macros: MacrosInfo

    @property
    def detail_text(self) -> str:
        """Formatted summary text: e.g. '950.0g · $20.50 · 1045 kcal'."""
        return f"{self.grams:.1f}g · ${self.cost:.2f} · {self.macros.calories_kcal:.0f} kcal"


@dataclass(frozen=True)
class PreparedRecipe:
    """Complete precomputed mathematical and nutritional data for a recipe."""
    recipe: "Recipe"
    servings: int
    raw_batch_weight_g: float
    cooked_batch_weight_g: float
    portion_cooked_weight_g: float
    cooking_loss_percent: float
    batch_cost: float
    serving_cost: float
    safe_fridge_days: int
    freezer_friendly: bool
    batch_macros: MacrosInfo
    serving_macros: MacrosInfo
    ingredients: list[IngredientBreakdown]
    equipment_names: list[str]

    @property
    def id(self) -> str:
        return self.recipe.id

    @property
    def title(self) -> str:
        return self.recipe.title

    @property
    def category(self) -> str:
        return self.recipe.category.value

    def review_math(self) -> str:
        """Generate a clean, readable text audit of all calculations."""
        servings_display = f"{self.servings:g}"
        lines = [
            "=" * 80,
            f"MATH AUDIT: {self.title} ({self.category})",
            f"Yield: {servings_display} servings | Cooked: {self.cooked_batch_weight_g:.1f}g "
            f"({self.portion_cooked_weight_g:.1f}g / serving) | Loss: {self.cooking_loss_percent:.1f}%",
            f"Storage: {self.safe_fridge_days} days fridge | Freezer Friendly: {'Yes' if self.freezer_friendly else 'No'}",
            f"Cost: ${self.batch_cost:.2f} batch | ${self.serving_cost:.2f} / serving",
            "-" * 80,
            "INGREDIENT CONTRIBUTIONS:",
        ]

        for item in self.ingredients:
            m = item.macros
            lines.append(
                f"  - {item.name:<32} {item.quantity:g} {item.unit:<5} -> "
                f"{item.grams:6.1f}g | ${item.cost:5.2f} | "
                f"{m.calories_kcal:4.0f} kcal | P: {m.protein_g:5.1f}g | F: {m.fat_g:5.1f}g | C: {m.carbs_g:5.1f}g"
            )

        lines.extend([
            "-" * 80,
            "BATCH TOTALS:",
            f"  Weight: {self.raw_batch_weight_g:.1f}g raw -> {self.cooked_batch_weight_g:.1f}g cooked (-{self.cooking_loss_percent:.1f}% loss)",
            f"  Cost:   ${self.batch_cost:.2f} CAD",
            f"  Macros: {self.batch_macros.calories_kcal:.0f} kcal | Protein: {self.batch_macros.protein_g:.1f}g | "
            f"Fat: {self.batch_macros.fat_g:.1f}g (Sat: {self.batch_macros.saturated_fat_g or 0:.1f}g) | "
            f"Carbs: {self.batch_macros.carbs_g:.1f}g (Fiber: {self.batch_macros.fiber_g:.1f}g, Sugars: {self.batch_macros.sugars_g or 0:.1f}g) | "
            f"Sodium: {self.batch_macros.sodium_mg or 0:.0f} mg | Potassium: {self.batch_macros.potassium_mg or 0:.0f} mg",
            "-" * 80,
            f"PER PORTION (/ {servings_display}):",
            f"  Portion Scale Weight: {self.portion_cooked_weight_g:.1f}g cooked",
            f"  Cost per Serving:     ${self.serving_cost:.2f} CAD",
            f"  Macros per Serving:   {self.serving_macros.calories_kcal:.0f} kcal | "
            f"Protein: {self.serving_macros.protein_g:.1f}g | Fat: {self.serving_macros.fat_g:.1f}g (Sat: {self.serving_macros.saturated_fat_g or 0:.1f}g) | "
            f"Carbs: {self.serving_macros.carbs_g:.1f}g (Fiber: {self.serving_macros.fiber_g:.1f}g, Sugars: {self.serving_macros.sugars_g or 0:.1f}g) | "
            f"Sodium: {self.serving_macros.sodium_mg or 0:.0f} mg | Potassium: {self.serving_macros.potassium_mg or 0:.0f} mg",
            "=" * 80,
        ])
        return "\n".join(lines)


def prepare_recipe(
    recipe: "Recipe",
    catalog: dict[str, "Ingredient"],
    units: "UnitsRegistry",
    equipment: "EquipmentRegistry | None" = None,
) -> PreparedRecipe:
    """Perform all mathematical and nutritional computations for a recipe.

    Args:
        recipe: Parsed Recipe model with instructions, yield, and frontmatter.
        catalog: Loaded ingredients catalog dictionary (id -> Ingredient).
        units: UnitsRegistry containing universal physics conversions.
        equipment: Optional EquipmentRegistry for resolving canonical names.

    Returns:
        PreparedRecipe containing precomputed batch and serving values ready for display or review.
    """
    ingredient_breakdowns: list[IngredientBreakdown] = []
    total_raw_g = 0.0
    total_cost = 0.0

    batch_macros_dict: dict[str, float] = {
        "calories_kcal": 0.0,
        "protein_g": 0.0,
        "fat_g": 0.0,
        "saturated_fat_g": 0.0,
        "carbs_g": 0.0,
        "fiber_g": 0.0,
        "sugars_g": 0.0,
        "sodium_mg": 0.0,
        "potassium_mg": 0.0,
    }

    min_safe_days = recipe.storage_info.fridge_days

    for item in recipe.ingredients:
        if item.id not in catalog:
            raise ValueError(f"Ingredient '{item.id}' in recipe '{recipe.id}' not found in catalog")

        ing = catalog[item.id]
        grams = ing.convert(item.quantity, item.unit, "g", units=units)
        factor = grams / 100.0
        item_cost = factor * price_per_100g(ing, units)

        total_raw_g += grams
        total_cost += item_cost
        min_safe_days = min(min_safe_days, ing.shelf_life_days)

        # Compute item-level macro contribution
        m = ing.macros_per_100g
        item_macros_dict: dict[str, float] = {}
        for key in batch_macros_dict:
            val = getattr(m, key, 0.0) or 0.0
            contrib = val * factor
            item_macros_dict[key] = round(contrib, 2)
            batch_macros_dict[key] += contrib

        item_macros = MacrosInfo.model_validate(item_macros_dict)

        ingredient_breakdowns.append(
            IngredientBreakdown(
                id=item.id,
                name=ing.name,
                aisle=ing.aisle,
                quantity=item.quantity,
                unit=item.unit,
                grams=round(grams, 1),
                cost=round(item_cost, 2),
                macros=item_macros,
            )
        )

    # Finalize batch calculations
    raw_batch_weight_g = round(total_raw_g, 1)
    cooked_batch_weight_g = float(recipe.yield_info.cooked_g)
    servings = recipe.yield_info.servings

    cooking_loss_percent = 0.0
    if raw_batch_weight_g > 0:
        cooking_loss_percent = round((1.0 - (cooked_batch_weight_g / raw_batch_weight_g)) * 100.0, 1)

    batch_cost = round(total_cost, 2)
    serving_cost = round(batch_cost / servings, 2)
    portion_cooked_weight_g = round(cooked_batch_weight_g / servings, 1)

    # Round batch macros
    for key in batch_macros_dict:
        batch_macros_dict[key] = round(batch_macros_dict[key], 1)
    batch_macros = MacrosInfo.model_validate(batch_macros_dict)

    # Compute per-serving macros
    serving_macros_dict = {
        key: round(batch_macros_dict[key] / servings, 1)
        for key in batch_macros_dict
    }
    serving_macros = MacrosInfo.model_validate(serving_macros_dict)

    # Resolve equipment names
    equipment_names: list[str] = []
    for eq_id in recipe.equipment:
        if equipment:
            eq_item = equipment.get(eq_id)
            name = eq_item.name if eq_item else eq_id.replace("-", " ").title()
        else:
            name = eq_id.replace("-", " ").title()
        equipment_names.append(name)

    return PreparedRecipe(
        recipe=recipe,
        servings=servings,
        raw_batch_weight_g=raw_batch_weight_g,
        cooked_batch_weight_g=cooked_batch_weight_g,
        portion_cooked_weight_g=portion_cooked_weight_g,
        cooking_loss_percent=cooking_loss_percent,
        batch_cost=batch_cost,
        serving_cost=serving_cost,
        safe_fridge_days=min_safe_days,
        freezer_friendly=recipe.storage_info.freezer_friendly,
        batch_macros=batch_macros,
        serving_macros=serving_macros,
        ingredients=ingredient_breakdowns,
        equipment_names=equipment_names,
    )
