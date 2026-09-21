"""Recipe model and Cooklang parser.

Parses .cook files containing YAML frontmatter and Cooklang body markup.
Performs semantic cross-validation against ingredients catalog, equipment registry,
and units registry, and deterministically computes batch/serving weights, macros, and costs.
"""

from pathlib import Path
import re
from typing import Any
import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator
from meal_prep.models.enums import RecipeCategory
from meal_prep.models.ingredient import Ingredient, MacrosInfo
from meal_prep.models.units import UnitsRegistry
from meal_prep.models.equipment import EquipmentRegistry


class RecipeYield(BaseModel):
    servings: float = Field(..., gt=0, description="Number of portions produced by the batch")
    cooked_g: float = Field(..., gt=0, description="Total finished cooked batch weight in grams")


class RecipeStorage(BaseModel):
    fridge_days: int = Field(..., gt=0, description="Maximum safe refrigerated shelf life in days")
    freezer_friendly: bool = Field(..., description="Whether the cooked batch can be frozen")


class RecipeFrontmatter(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Unique alphanumeric slug with hyphens matching file stem")
    title: str = Field(..., min_length=1, description="Human-readable recipe title")
    category: RecipeCategory = Field(..., description="Recipe category enum")
    yield_info: RecipeYield = Field(..., alias="yield", description="Portion count and cooked batch weight")
    storage_info: RecipeStorage = Field(..., alias="storage", description="Storage specifications")
    equipment: list[str] = Field(..., min_length=1, description="List of equipment IDs required")

    @field_validator("id")
    @classmethod
    def validate_id_format(cls, v: str) -> str:
        clean = v.strip().lower()
        if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", clean):
            raise ValueError(f"Recipe id '{v}' must be alphanumeric with hyphens (kebab-case)")
        return clean


class RecipeIngredientRef(BaseModel):
    id: str = Field(..., description="Ingredient identifier matching catalog id")
    quantity: float = Field(..., gt=0, description="Quantity used in recipe")
    unit: str = Field(..., min_length=1, description="Measurement unit (must convert to grams)")


class RecipeCookwareRef(BaseModel):
    id: str = Field(..., description="Equipment identifier or canonical name")


class RecipeTimerRef(BaseModel):
    name: str = Field(..., description="Timer description or name")
    duration: float = Field(..., gt=0, description="Timer duration value")
    unit: str = Field(..., min_length=1, description="Time unit (s, min, hr)")


class Recipe(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    title: str
    category: RecipeCategory
    yield_info: RecipeYield = Field(..., alias="yield")
    storage_info: RecipeStorage = Field(..., alias="storage")
    equipment: list[str]
    ingredients: list[RecipeIngredientRef]
    cookware: list[RecipeCookwareRef]
    timers: list[RecipeTimerRef]
    instructions: str
    source_path: Path | None = None

    @property
    def portion_cooked_weight_g(self) -> float:
        """Portion weight in grams per serving."""
        return round(self.yield_info.cooked_g / self.yield_info.servings, 1)

    def compute_raw_batch_weight_g(
        self,
        catalog: dict[str, Ingredient],
        units: UnitsRegistry,
    ) -> float:
        """Compute total raw un-cooked batch weight in grams."""
        total_g = 0.0
        for item in self.ingredients:
            if item.id not in catalog:
                raise ValueError(f"Ingredient '{item.id}' in recipe '{self.id}' not found in ingredients catalog")
            ing = catalog[item.id]
            grams = ing.convert(item.quantity, item.unit, "g", units=units)
            total_g += grams
        return round(total_g, 1)

    def compute_cooking_loss_percent(
        self,
        catalog: dict[str, Ingredient],
        units: UnitsRegistry,
    ) -> float:
        """Compute cooking/moisture yield loss percentage."""
        raw_g = self.compute_raw_batch_weight_g(catalog, units)
        if raw_g <= 0:
            return 0.0
        loss = (1.0 - (self.yield_info.cooked_g / raw_g)) * 100.0
        return round(loss, 1)

    def compute_macros(
        self,
        catalog: dict[str, Ingredient],
        units: UnitsRegistry,
    ) -> tuple[MacrosInfo, MacrosInfo]:
        """Compute total batch macros and per-serving macros.
        
        Returns:
            (batch_macros, serving_macros)
        """
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

        for item in self.ingredients:
            if item.id not in catalog:
                raise ValueError(f"Ingredient '{item.id}' in recipe '{self.id}' not found in ingredients catalog")
            ing = catalog[item.id]
            grams = ing.convert(item.quantity, item.unit, "g", units=units)
            factor = grams / 100.0

            m = ing.macros_per_100g
            for key in batch_macros_dict:
                val = getattr(m, key, 0.0) or 0.0
                batch_macros_dict[key] += val * factor

        # Round batch macros
        for key in batch_macros_dict:
            batch_macros_dict[key] = round(batch_macros_dict[key], 1)

        batch_macros = MacrosInfo.model_validate(batch_macros_dict)

        # Compute per-serving macros
        servings = self.yield_info.servings
        serving_macros_dict = {
            key: round(batch_macros_dict[key] / servings, 1)
            for key in batch_macros_dict
        }
        serving_macros = MacrosInfo.model_validate(serving_macros_dict)

        return batch_macros, serving_macros

    def compute_cost(
        self,
        catalog: dict[str, Ingredient],
        units: UnitsRegistry,
    ) -> tuple[float, float]:
        """Compute estimated batch retail cost and cost per serving in CAD.
        
        Returns:
            (batch_cost, serving_cost)
        """
        total_cost = 0.0
        for item in self.ingredients:
            if item.id not in catalog:
                raise ValueError(f"Ingredient '{item.id}' in recipe '{self.id}' not found in ingredients catalog")
            ing = catalog[item.id]
            grams = ing.convert(item.quantity, item.unit, "g", units=units)
            item_cost = (grams / 100.0) * ing.price_per_100g
            total_cost += item_cost

        batch_cost = round(total_cost, 2)
        serving_cost = round(batch_cost / self.yield_info.servings, 2)
        return batch_cost, serving_cost

    def compute_safe_fridge_days(self, catalog: dict[str, Ingredient]) -> int:
        """Compute safe fridge storage window constrained by ingredient shelf life."""
        safe_days = self.storage_info.fridge_days
        for item in self.ingredients:
            if item.id in catalog:
                safe_days = min(safe_days, catalog[item.id].shelf_life_days)
        return safe_days


# Regex patterns for Cooklang elements
_INGREDIENT_PATTERN = re.compile(
    r"@(?:([a-zA-Z0-9_-]+|\b[a-zA-Z0-9_ -]+?)\s*\{\s*([^}%]*?)\s*(?:%\s*([^}]+?)\s*)?\}|([a-zA-Z0-9_-]+))"
)
_COOKWARE_PATTERN = re.compile(
    r"#([a-zA-Z0-9_-]+|\b[a-zA-Z0-9_ -]+?)\s*\{\}|#([a-zA-Z0-9_-]+)"
)
_TIMER_PATTERN = re.compile(
    r"~([a-zA-Z0-9_-]+)?\s*\{\s*([^}%]+)\s*%\s*([^}]+)\s*\}"
)


def parse_cooklang_body(text: str) -> tuple[list[RecipeIngredientRef], list[RecipeCookwareRef], list[RecipeTimerRef]]:
    """Extract ingredients, cookware, and timers from Cooklang instructions text."""
    ingredients: list[RecipeIngredientRef] = []
    cookware: list[RecipeCookwareRef] = []
    timers: list[RecipeTimerRef] = []

    # 1. Parse Ingredients
    for match in _INGREDIENT_PATTERN.finditer(text):
        if match.group(1):
            name = match.group(1).strip().lower()
            qty_raw = match.group(2).strip() if match.group(2) else None
            unit_raw = match.group(3).strip().lower() if match.group(3) else None
        else:
            name = match.group(4).strip().lower()
            qty_raw = None
            unit_raw = None

        if not qty_raw or not unit_raw:
            raise ValueError(
                f"Ingredient '@{name}' in recipe missing quantity or unit. "
                "All ingredients must specify '{quantity%unit}' for deterministic macro and cost tracking."
            )

        try:
            qty = float(qty_raw)
        except ValueError:
            raise ValueError(f"Invalid quantity '{qty_raw}' for ingredient '@{name}'. Must be a numeric value.")

        if qty <= 0:
            raise ValueError(f"Quantity for ingredient '@{name}' must be positive, got {qty}.")

        ingredients.append(RecipeIngredientRef(id=name, quantity=qty, unit=unit_raw))

    # 2. Parse Cookware
    seen_cookware = set()
    for match in _COOKWARE_PATTERN.finditer(text):
        item_id = (match.group(1) or match.group(2)).strip().lower()
        if item_id not in seen_cookware:
            seen_cookware.add(item_id)
            cookware.append(RecipeCookwareRef(id=item_id))

    # 3. Parse Timers
    for match in _TIMER_PATTERN.finditer(text):
        name = (match.group(1) or "timer").strip()
        duration_raw = match.group(2).strip()
        unit_raw = match.group(3).strip().lower()

        try:
            duration = float(duration_raw)
        except ValueError:
            raise ValueError(f"Invalid timer duration '{duration_raw}' for timer '{name}'. Must be a numeric value.")

        if duration <= 0:
            raise ValueError(f"Timer duration for '{name}' must be positive, got {duration}.")

        timers.append(RecipeTimerRef(name=name, duration=duration, unit=unit_raw))

    return ingredients, cookware, timers


def split_recipe_file(content: str) -> tuple[dict[str, Any], str]:
    """Split .cook file into YAML frontmatter dictionary and instructions body text."""
    stripped = content.strip()
    if not stripped.startswith("---"):
        raise ValueError("Invalid recipe file: must begin with YAML frontmatter delimiter '---'")

    parts = stripped.split("---", 2)
    if len(parts) < 3:
        raise ValueError("Invalid recipe file: missing closing frontmatter delimiter '---'")

    frontmatter_yaml = parts[1]
    instructions = parts[2].strip()

    try:
        raw_frontmatter = yaml.safe_load(frontmatter_yaml)
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse YAML frontmatter: {e}")

    if not isinstance(raw_frontmatter, dict):
        raise ValueError("Recipe frontmatter must be a YAML mapping/dictionary")

    return raw_frontmatter, instructions


def load_recipe_file(
    path: Path | str,
    catalog: dict[str, Ingredient] | None = None,
    equipment_reg: EquipmentRegistry | None = None,
    units_reg: UnitsRegistry | None = None,
) -> Recipe:
    """Load, parse, and validate a .cook recipe file.
    
    If catalog, equipment_reg, and units_reg are provided, executes full semantic cross-validation:
    - Verifies ingredient existence and unit conversion to grams
    - Verifies equipment IDs against equipment registry
    - Verifies timer units against time units in units registry
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Recipe file not found: {file_path}")

    with file_path.open("r", encoding="utf-8") as f:
        content = f.read()

    raw_frontmatter, instructions = split_recipe_file(content)

    # Validate frontmatter via Pydantic model
    frontmatter = RecipeFrontmatter.model_validate(raw_frontmatter)

    # Verify ID matches filename stem
    expected_id = file_path.stem
    if frontmatter.id != expected_id:
        raise ValueError(
            f"Recipe ID '{frontmatter.id}' does not match filename stem '{expected_id}' in {file_path}"
        )

    # Verify category matches parent directory name
    expected_cat = file_path.parent.name
    if frontmatter.category.value != expected_cat:
        raise ValueError(
            f"Recipe '{frontmatter.id}' category '{frontmatter.category.value}' "
            f"does not match parent directory '{expected_cat}'"
        )

    # Parse Cooklang body
    ingredients, cookware, timers = parse_cooklang_body(instructions)

    if not ingredients:
        raise ValueError(f"Recipe '{frontmatter.id}' has no ingredients declared in instructions body.")

    # Contextual Cross-Validation if registries provided
    if units_reg is not None:
        # Validate timer units
        for timer in timers:
            if not units_reg.is_valid_time_unit(timer.unit):
                raise ValueError(
                    f"Timer '{timer.name}' in recipe '{frontmatter.id}' specifies invalid time unit '{timer.unit}'. "
                    f"Must be a registered time unit (s, min, hr)."
                )

    if equipment_reg is not None:
        # Validate frontmatter equipment list
        for eq_id in frontmatter.equipment:
            if equipment_reg.get(eq_id) is None:
                raise ValueError(
                    f"Recipe '{frontmatter.id}' declares unknown equipment ID '{eq_id}'. "
                    "Must exist in data/equipment.yaml"
                )

        # Validate body cookware references
        for cw in cookware:
            if equipment_reg.get(cw.id) is None:
                raise ValueError(
                    f"Recipe '{frontmatter.id}' mentions unknown cookware '#{cw.id}' in instructions. "
                    "Must exist in data/equipment.yaml"
                )

    if catalog is not None and units_reg is not None:
        # Validate ingredients and unit conversions to grams
        for item in ingredients:
            if item.id not in catalog:
                raise ValueError(
                    f"Recipe '{frontmatter.id}' uses ingredient '@{item.id}' which does not exist in ingredients catalog!"
                )
            ing = catalog[item.id]
            graph = ing.get_conversion_graph(units_reg)
            if not graph.can_convert(item.unit, "g"):
                raise ValueError(
                    f"Recipe '{frontmatter.id}' calls for '@{item.id}{{{item.quantity}%{item.unit}}}', "
                    f"but unit '{item.unit}' cannot be converted to grams for this ingredient."
                )

    return Recipe(
        id=frontmatter.id,
        title=frontmatter.title,
        category=frontmatter.category,
        yield_info=frontmatter.yield_info,
        storage_info=frontmatter.storage_info,
        equipment=frontmatter.equipment,
        ingredients=ingredients,
        cookware=cookware,
        timers=timers,
        instructions=instructions,
        source_path=file_path,
    )


def load_all_recipes(
    recipes_dir: Path | str = Path("recipes"),
    catalog: dict[str, Ingredient] | None = None,
    equipment_reg: EquipmentRegistry | None = None,
    units_reg: UnitsRegistry | None = None,
) -> dict[str, Recipe]:
    """Load and validate all .cook recipe files across all category directories."""
    directory = Path(recipes_dir)
    if not directory.exists() or not directory.is_dir():
        raise FileNotFoundError(f"Recipes directory not found: {directory}")

    recipes: dict[str, Recipe] = {}
    for cook_file in sorted(directory.rglob("*.cook")):
        recipe = load_recipe_file(
            cook_file,
            catalog=catalog,
            equipment_reg=equipment_reg,
            units_reg=units_reg,
        )
        if recipe.id in recipes:
            raise ValueError(f"Duplicate recipe ID '{recipe.id}' found across multiple files!")
        recipes[recipe.id] = recipe

    return recipes
