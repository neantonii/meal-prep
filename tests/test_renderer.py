"""Tests for the root-level recipe card renderer (``renderer.py``).

Covers the presentation concern this module owns: which name is shown where.
The instruction-step badges use the ingredient's ``step_name`` (prose-friendly)
while the tooltip title and the shopping checklist keep the full ``name``.
"""

from __future__ import annotations

import renderer
from meal_prep.enums import RecipeCategory
from meal_prep.models.ingredient import MacrosInfo
from meal_prep.models.recipe import Recipe, RecipeIngredient


def _macros() -> MacrosInfo:
    return MacrosInfo(
        calories_kcal=100.0,
        protein_g=10.0,
        fat_g=5.0,
        carbs_g=20.0,
        fiber_g=1.0,
        saturated_fat_g=0.0,
        sugars_g=0.0,
        sodium_mg=0.0,
        potassium_mg=0.0,
    )


def _recipe() -> Recipe:
    return Recipe(
        id="test",
        title="Test",
        category=RecipeCategory.MODULAR_PROTEIN,
        servings=1.0,
        cooked_g=200.0,
        fridge_days=3,
        freezer_friendly=False,
        equipment=(),
        cookware_by_token={},
        ingredients=(
            RecipeIngredient(
                id="boneless-chicken-breast",
                name="Boneless, Skinless Chicken Breast",
                step_name="chicken breasts",
                quantity=4.0,
                unit="piece",
                grams=950.0,
                cost=22.61,
                macros=_macros(),
            ),
        ),
        instructions="Trim any excess fat from @boneless-chicken-breast{4%piece}.",
    )


def test_step_badge_uses_step_name():
    html = renderer.render_recipe_card(_recipe())
    # Visible badge text uses the prose-friendly short noun (amount omitted:
    # the ingredient is declared only once).
    assert '>chicken breasts</span>' in html
    # Full canonical name is present only as a tooltip.
    assert 'title="Ingredient: Boneless, Skinless Chicken Breast">chicken breasts' in html


def test_checklist_uses_full_name():
    html = renderer.render_recipe_card(_recipe())
    assert '<span class="ing-name">Boneless, Skinless Chicken Breast</span>' in html


def test_step_name_falls_back_to_full_name():
    recipe = _recipe()
    # Rebuild with step_name == full name (the service default when unset).
    from dataclasses import replace

    ing = replace(recipe.ingredients[0], step_name="Boneless, Skinless Chicken Breast")
    recipe = replace(recipe, ingredients=(ing,))
    html = renderer.render_recipe_card(recipe)
    assert '>Boneless, Skinless Chicken Breast</span>' in html


def test_step_badge_shows_amount_when_repeated():
    from dataclasses import replace

    recipe = _recipe()
    ing = replace(recipe.ingredients[0], repeated=True)
    recipe = replace(recipe, ingredients=(ing,))
    html = renderer.render_recipe_card(recipe)
    # A repeated declaration keeps its inline amount to disambiguate steps.
    assert '>4 piece chicken breasts</span>' in html


def test_checklist_drops_count_unit():
    from dataclasses import replace

    recipe = _recipe()
    ing = replace(recipe.ingredients[0], quantity=4.0, unit="count")
    recipe = replace(recipe, ingredients=(ing,))
    html = renderer.render_recipe_card(recipe)
    assert '<span class="ing-qty">4</span>' in html
    assert "<span class=\"ing-qty\">4 count</span>" not in html


def test_interpolated_values_are_html_escaped():
    from dataclasses import replace

    recipe = _recipe()
    recipe = replace(recipe, title='A <script>alert(1)</script> & "Title"')
    ing = replace(
        recipe.ingredients[0],
        name='X & <Y> "Z"',
        step_name='x & <y>',
    )
    recipe = replace(recipe, ingredients=(ing,), equipment=('Oven & <Rack>',))

    html = renderer.render_recipe_card(recipe)

    # Title is escaped in both <title> and <h1>.
    assert '<title>A &lt;script&gt;alert(1)&lt;/script&gt; &amp; &quot;Title&quot; — Meal Prep Recipe</title>' in html
    assert '<h1 class="recipe-title">A &lt;script&gt;alert(1)&lt;/script&gt; &amp; &quot;Title&quot;</h1>' in html
    # Ingredient checklist name is escaped.
    assert '<span class="ing-name">X &amp; &lt;Y&gt; &quot;Z&quot;</span>' in html
    # Ingredient step badge (title + visible) is escaped.
    assert 'title="Ingredient: X &amp; &lt;Y&gt; &quot;Z&quot;">x &amp; &lt;y&gt;' in html
    # Equipment badge is escaped.
    assert 'Oven &amp; &lt;Rack&gt;' in html
    # No raw, unescaped dangerous fragment survives.
    assert '<script>alert(1)</script>' not in html
