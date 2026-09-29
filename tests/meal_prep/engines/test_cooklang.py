"""Tests for the pure Cooklang tokenizer/parser (``engines/cooklang.py``).

Covers happy paths plus the engine's own syntax errors (missing quantity/unit,
non-numeric or non-positive quantities, and malformed timers). Timers are
validated in place but deliberately not surfaced as records.
"""

from __future__ import annotations

import pytest

from meal_prep.engines.cooklang import (
    CooklangCookware,
    CooklangIngredient,
    CooklangMention,
    parse_cooklang,
)

# ---------------------------------------------------------------------------
# happy paths — ingredients
# ---------------------------------------------------------------------------


def test_parse_single_ingredient():
    doc = parse_cooklang("Add @salt{1%tsp} to taste")
    assert doc.ingredients == (
        CooklangIngredient(name="salt", quantity=1.0, unit="tsp"),
    )
    assert doc.cookware == ()


def test_parse_decimal_quantity():
    doc = parse_cooklang("@salt{1.5%tbsp}")
    assert doc.ingredients[0].quantity == 1.5


def test_parse_multiple_ingredients_in_order():
    doc = parse_cooklang("@oil{2%tbsp} then @chicken{500%g}")
    names = [i.name for i in doc.ingredients]
    assert names == ["oil", "chicken"]


def test_ingredient_name_is_lowercased_and_trimmed():
    doc = parse_cooklang("@SALT{1%tsp}")
    assert doc.ingredients[0].name == "salt"


def test_multi_word_ingredient_name_preserved():
    doc = parse_cooklang("@olive oil{1%tbsp}")
    assert doc.ingredients[0].name == "olive oil"


def test_unit_is_lowercased():
    doc = parse_cooklang("@salt{1%TSP}")
    assert doc.ingredients[0].unit == "tsp"


# ---------------------------------------------------------------------------
# happy paths — cookware
# ---------------------------------------------------------------------------


def test_parse_cookware_bare():
    doc = parse_cooklang("Cook in #pan")
    assert doc.cookware == (CooklangCookware(id="pan"),)


def test_parse_cookware_with_empty_braces():
    doc = parse_cooklang("Cook in #pan{}")
    assert doc.cookware == (CooklangCookware(id="pan"),)


def test_cookware_name_is_lowercased_and_trimmed():
    doc = parse_cooklang("#PAN")
    assert doc.cookware[0].id == "pan"


def test_duplicate_cookware_is_deduplicated():
    doc = parse_cooklang("#pan and #pan and #pan")
    assert doc.cookware == (CooklangCookware(id="pan"),)


# ---------------------------------------------------------------------------
# happy paths — timers (validated but not surfaced)
# ---------------------------------------------------------------------------


def test_named_timer_is_validated_and_not_surfaced():
    doc = parse_cooklang("Bake ~rest{5%min} then serve")
    assert doc.ingredients == ()
    assert doc.cookware == ()


def test_unnamed_timer_is_validated():
    doc = parse_cooklang("~{5%min}")
    assert doc.ingredients == ()
    assert doc.cookware == ()


@pytest.mark.parametrize(
    "unit", ["s", "sec", "seconds", "min", "mins", "minute", "hr", "hours"]
)
def test_timer_accepts_all_registered_time_units(unit):
    parse_cooklang(f"~rest{{5%{unit}}}")


# ---------------------------------------------------------------------------
# happy paths — empty / no markup
# ---------------------------------------------------------------------------


def test_empty_text_yields_empty_document():
    doc = parse_cooklang("")
    assert doc.ingredients == ()
    assert doc.cookware == ()


def test_plain_text_without_markup_yields_empty_document():
    doc = parse_cooklang("Season and cook until done.")
    assert doc.ingredients == ()
    assert doc.cookware == ()


# ---------------------------------------------------------------------------
# errors — ingredients
# ---------------------------------------------------------------------------


def test_bare_ingredient_is_a_mention_not_an_error():
    doc = parse_cooklang("@salt")
    assert doc.ingredients == ()
    assert doc.mentions == (CooklangMention(name="salt"),)


def test_empty_brace_ingredient_is_a_mention():
    doc = parse_cooklang("@salt{}")
    assert doc.ingredients == ()
    assert doc.mentions == (CooklangMention(name="salt"),)


def test_ingredient_without_unit_is_a_count():
    doc = parse_cooklang("@salt{1}")
    assert doc.ingredients == (CooklangIngredient(name="salt", quantity=1.0, unit=""),)


def test_ingredient_with_unit_but_no_quantity_is_rejected():
    with pytest.raises(ValueError, match="missing quantity"):
        parse_cooklang("@salt{%tsp}")


def test_ingredient_with_empty_unit_is_rejected():
    with pytest.raises(ValueError, match="empty unit"):
        parse_cooklang("@salt{1%}")


def test_ingredient_with_whitespace_only_unit_is_rejected():
    with pytest.raises(ValueError, match="empty unit"):
        parse_cooklang("@salt{1%   }")


def test_ingredient_non_numeric_quantity_is_rejected():
    with pytest.raises(ValueError, match="Invalid quantity 'abc'"):
        parse_cooklang("@salt{abc%tsp}")


def test_ingredient_zero_quantity_is_rejected():
    with pytest.raises(ValueError, match="must be positive, got 0.0"):
        parse_cooklang("@salt{0%tsp}")


def test_ingredient_negative_quantity_is_rejected():
    with pytest.raises(ValueError, match="must be positive, got -1.0"):
        parse_cooklang("@salt{-1%tsp}")


# ---------------------------------------------------------------------------
# errors — timers
# ---------------------------------------------------------------------------


def test_timer_non_numeric_duration_is_rejected():
    with pytest.raises(ValueError, match="Invalid timer duration 'abc'"):
        parse_cooklang("~rest{abc%min}")


def test_timer_zero_duration_is_rejected():
    with pytest.raises(ValueError, match="must be positive, got 0.0"):
        parse_cooklang("~rest{0%min}")


def test_timer_negative_duration_is_rejected():
    with pytest.raises(ValueError, match="must be positive, got -5.0"):
        parse_cooklang("~rest{-5%min}")


def test_timer_unknown_time_unit_is_rejected():
    with pytest.raises(ValueError, match="unknown time unit 'fortnight'"):
        parse_cooklang("~rest{5%fortnight}")
