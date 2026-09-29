"""Tests for the recipe Cooklang adapter (``adapters/recipes.py``).

Happy paths plus the adapter's own structure/consistency errors: frontmatter
delimiters and shape, ID/stem mismatch, category/directory mismatch, no
ingredients, missing file, missing directory, and duplicate IDs. Cooklang body
syntax errors are covered by ``test_cooklang.py`` and not re-tested here.
"""

from __future__ import annotations

import pytest

from meal_prep.adapters.recipes import (
    load_all_recipes,
    load_recipe_file,
    split_recipe_file,
)
from meal_prep.dtos.recipe import Recipe


def _cook(
    *,
    id_: str = "pan-fried-ground-turkey",
    category: str = "modular_protein",
    body: str = "Add @turkey{450%g}.\n",
) -> str:
    return (
        "---\n"
        f"id: {id_}\n"
        "title: Test Recipe\n"
        f"category: {category}\n"
        "yield:\n  servings: 2\n  cooked_g: 330\n"
        "storage:\n  fridge_days: 4\n  freezer_friendly: true\n"
        "---\n"
        f"{body}\n"
    )


def _write_file(tmp_path, filename: str, content: str):
    path = tmp_path / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# split_recipe_file — happy paths
# ---------------------------------------------------------------------------


def test_split_recipe_file_valid():
    frontmatter, body = split_recipe_file(_cook())
    assert frontmatter["id"] == "pan-fried-ground-turkey"
    assert "Add @turkey" in body


# ---------------------------------------------------------------------------
# split_recipe_file — structure errors
# ---------------------------------------------------------------------------


def test_split_recipe_file_rejects_missing_opening_delimiter():
    with pytest.raises(ValueError, match="must begin with YAML frontmatter"):
        split_recipe_file("id: x\n---\nbody\n")


def test_split_recipe_file_rejects_missing_closing_delimiter():
    with pytest.raises(ValueError, match="missing closing frontmatter delimiter"):
        split_recipe_file("---\nid: x\n")


def test_split_recipe_file_rejects_non_mapping_frontmatter():
    with pytest.raises(ValueError, match="must be a YAML mapping"):
        split_recipe_file("---\n- a\n- b\n---\nbody\n")


def test_split_recipe_file_rejects_invalid_frontmatter_yaml():
    with pytest.raises(ValueError, match="Failed to parse YAML frontmatter"):
        split_recipe_file("---\nkey: [unclosed\n---\nbody\n")


# ---------------------------------------------------------------------------
# load_recipe_file — happy paths
# ---------------------------------------------------------------------------


def test_load_recipe_file_valid(tmp_path):
    path = _write_file(tmp_path, "modular_protein/pan-fried-ground-turkey.cook", _cook())
    recipe = load_recipe_file(path)
    assert isinstance(recipe, Recipe)
    assert recipe.id == "pan-fried-ground-turkey"
    assert recipe.ingredients[0].id == "turkey"
    assert recipe.source_path == path


def test_load_recipe_file_captures_mentions_and_counts(tmp_path):
    body = "Add @turkey{1} then cook the @turkey{} through.\n"
    path = _write_file(tmp_path, "modular_protein/pan-fried-ground-turkey.cook", _cook(body=body))
    recipe = load_recipe_file(path)
    assert recipe.ingredients[0].id == "turkey"
    assert recipe.ingredients[0].unit == ""
    assert [m.id for m in recipe.mentions] == ["turkey"]


# ---------------------------------------------------------------------------
# load_recipe_file — errors
# ---------------------------------------------------------------------------


def test_load_recipe_file_missing_file():
    with pytest.raises(FileNotFoundError, match="Recipe file not found"):
        load_recipe_file("/nonexistent/recipe.cook")


def test_load_recipe_file_id_stem_mismatch(tmp_path):
    path = _write_file(tmp_path, "modular_protein/wrong-stem.cook", _cook(id_="other-id"))
    with pytest.raises(ValueError, match="does not match filename stem 'wrong-stem'"):
        load_recipe_file(path)


def test_load_recipe_file_category_directory_mismatch(tmp_path):
    path = _write_file(tmp_path, "breakfast/recipe.cook", _cook(id_="recipe", category="modular_protein"))
    with pytest.raises(ValueError, match="does not match parent directory 'breakfast'"):
        load_recipe_file(path)


def test_load_recipe_file_no_ingredients_is_rejected(tmp_path):
    path = _write_file(tmp_path, "modular_protein/recipe.cook", _cook(id_="recipe", body="Just cook.\n"))
    with pytest.raises(ValueError, match="has no ingredients declared"):
        load_recipe_file(path)


# ---------------------------------------------------------------------------
# load_all_recipes — happy paths
# ---------------------------------------------------------------------------


def test_load_all_recipes_valid(tmp_path):
    _write_file(tmp_path, "modular_protein/a.cook", _cook(id_="a"))
    _write_file(tmp_path, "breakfast/b.cook", _cook(id_="b", category="breakfast"))
    recipes = load_all_recipes(tmp_path)
    assert set(recipes) == {"a", "b"}


# ---------------------------------------------------------------------------
# load_all_recipes — errors
# ---------------------------------------------------------------------------


def test_load_all_recipes_missing_directory():
    with pytest.raises(FileNotFoundError, match="Recipes directory not found"):
        load_all_recipes("/nonexistent/recipes")


def test_load_all_recipes_duplicate_id_is_rejected(tmp_path):
    _write_file(tmp_path, "modular_protein/a.cook", _cook(id_="a"))
    _write_file(tmp_path, "breakfast/a.cook", _cook(id_="a", category="breakfast"))
    with pytest.raises(ValueError, match="Duplicate recipe ID 'a'"):
        load_all_recipes(tmp_path)
