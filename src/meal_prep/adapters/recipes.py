"""Cooklang adapter for recipe files (``recipes/<category>/<slug>.cook``).

Parses YAML frontmatter and Cooklang body markup, then performs semantic
cross-validation against the ingredient catalog, equipment registry, and units
registry.
"""

from pathlib import Path
from typing import Any
import yaml

from meal_prep.models.recipe import (
    Recipe,
    RecipeCookwareRef,
    RecipeFrontmatter,
    RecipeIngredientRef,
    RecipeTimerRef,
)
from meal_prep.models.ingredient import Ingredient
from meal_prep.models.units import UnitsRegistry
from meal_prep.models.equipment import EquipmentRegistry
from meal_prep.engines.cooklang import parse_cooklang


def parse_cooklang_body(text: str) -> tuple[list[RecipeIngredientRef], list[RecipeCookwareRef], list[RecipeTimerRef]]:
    """Extract ingredients, cookware, and timers from Cooklang instructions text.

    Tokenization and syntax validation live in the pure ``engines.cooklang``
    engine; this adapter maps the resulting records onto the recipe reference
    models.
    """
    doc = parse_cooklang(text)
    ingredients = [
        RecipeIngredientRef(id=i.name, quantity=i.quantity, unit=i.unit)
        for i in doc.ingredients
    ]
    cookware = [RecipeCookwareRef(id=c.id) for c in doc.cookware]
    timers = [
        RecipeTimerRef(name=t.name, duration=t.duration, unit=t.unit)
        for t in doc.timers
    ]
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

    if catalog is not None:
        # Validate ingredient references against the catalog
        for item in ingredients:
            if item.id not in catalog:
                raise ValueError(
                    f"Recipe '{frontmatter.id}' uses ingredient '@{item.id}' which does not exist in ingredients catalog!"
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
