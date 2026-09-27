"""Cooklang adapter for recipe files (``recipes/<category>/<slug>.cook``).

Parses YAML frontmatter and Cooklang body markup into plain DTO records. No
cross-validation against the ingredient catalog, equipment registry, or units
registry happens here — that is enrichment, and lives in a service.
"""

from pathlib import Path
from typing import Any
import yaml

from meal_prep.dtos.recipe import (
    Recipe,
    RecipeCookwareRef,
    RecipeFrontmatter,
    RecipeIngredientRef,
)
from meal_prep.engines.cooklang import parse_cooklang


def parse_cooklang_body(text: str) -> tuple[list[RecipeIngredientRef], list[RecipeCookwareRef]]:
    """Extract ingredients and cookware from Cooklang instructions text.

    Tokenization and syntax validation live in the pure ``engines.cooklang``
    engine; this adapter maps the resulting records onto the recipe reference
    DTOs.
    """
    doc = parse_cooklang(text)
    ingredients = [
        RecipeIngredientRef(id=i.name, quantity=i.quantity, unit=i.unit)
        for i in doc.ingredients
    ]
    cookware = [RecipeCookwareRef(id=c.id) for c in doc.cookware]
    return ingredients, cookware


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


def load_recipe_file(path: Path | str) -> Recipe:
    """Load and parse a .cook recipe file into its authored DTO.

    Performs only deserialization and shape validation (frontmatter model,
    Cooklang syntax, ID/category/file-layout consistency). Cross-validation
    against the catalog and registries is enrichment and is not done here.
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
    ingredients, cookware = parse_cooklang_body(instructions)

    if not ingredients:
        raise ValueError(f"Recipe '{frontmatter.id}' has no ingredients declared in instructions body.")

    return Recipe(
        id=frontmatter.id,
        title=frontmatter.title,
        category=frontmatter.category,
        yield_info=frontmatter.yield_info,
        storage_info=frontmatter.storage_info,
        equipment=frontmatter.equipment,
        ingredients=ingredients,
        cookware=cookware,
        instructions=instructions,
        source_path=file_path,
    )


def load_all_recipes(recipes_dir: Path | str = Path("recipes")) -> dict[str, Recipe]:
    """Load and validate all .cook recipe files across all category directories."""
    directory = Path(recipes_dir)
    if not directory.exists() or not directory.is_dir():
        raise FileNotFoundError(f"Recipes directory not found: {directory}")

    recipes: dict[str, Recipe] = {}
    for cook_file in sorted(directory.rglob("*.cook")):
        recipe = load_recipe_file(cook_file)
        if recipe.id in recipes:
            raise ValueError(f"Duplicate recipe ID '{recipe.id}' found across multiple files!")
        recipes[recipe.id] = recipe

    return recipes
