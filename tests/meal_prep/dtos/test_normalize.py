"""Tests for shared DTO token normalization (``dtos/_normalize.py``).

These two functions are the *only* permitted string cleanups at the DTO
boundary: case-folding + whitespace trimming for arbitrary tokens, plus the
kebab-case slug convention for identifiers. Everything else (plural stripping,
alias resolution, unit inference) is deliberately out of scope here and lives in
services instead — so these tests pin down exactly that narrow contract.
"""

from __future__ import annotations

import pytest

from meal_prep.dtos._normalize import clean_token, normalize_slug


# ---------------------------------------------------------------------------
# normalize_slug — the kebab-case identifier convention
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("boneless-chicken-breast", "boneless-chicken-breast"),
        ("air-fryer", "air-fryer"),
        ("a", "a"),  # single character is a valid word
        ("123", "123"),  # numeric-only slug
        ("a1-b2", "a1-b2"),
        ("a-1", "a-1"),
    ],
)
def test_normalize_slug_accepts_valid_slugs(raw, expected):
    assert normalize_slug(raw, field="id") == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Boneless-Chicken-Breast", "boneless-chicken-breast"),
        ("  Boneless-Chicken-Breast  ", "boneless-chicken-breast"),
        ("AIR-FRYER", "air-fryer"),
    ],
)
def test_normalize_slug_lowercases_and_trims(raw, expected):
    assert normalize_slug(raw, field="id") == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",  # empty
        "   ",  # whitespace only
        "boneless_chicken",  # underscore, not hyphen
        "boneless chicken",  # internal space
        "boneless--chicken",  # double hyphen
        "-boneless",  # leading hyphen
        "boneless-",  # trailing hyphen
        "Boneless Chicken!",  # punctuation
        "café",  # non-ascii
    ],
)
def test_normalize_slug_rejects_invalid_slugs(raw):
    with pytest.raises(ValueError, match="kebab-case slug"):
        normalize_slug(raw, field="id")


def test_normalize_slug_error_includes_field_name():
    with pytest.raises(ValueError, match="recipe_id"):
        normalize_slug("bad_slug", field="recipe_id")


# ---------------------------------------------------------------------------
# clean_token — case-fold + trim, reject empty
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("piece", "piece"),
        ("Piece", "piece"),
        ("  PIECE  ", "piece"),
        ("Fluid Ounce", "fluid ounce"),  # multi-word alias: space preserved
        ("1/3 cup", "1/3 cup"),  # fractional token kept verbatim
    ],
)
def test_clean_token_lowercases_and_trims(raw, expected):
    assert clean_token(raw, field="unit") == expected


def test_clean_token_rejects_empty():
    with pytest.raises(ValueError, match="cannot be empty"):
        clean_token("", field="unit")


def test_clean_token_rejects_whitespace_only():
    with pytest.raises(ValueError, match="cannot be empty"):
        clean_token("   ", field="unit")


def test_clean_token_error_includes_field_name():
    with pytest.raises(ValueError, match="alias"):
        clean_token("", field="alias")


def test_clean_token_does_not_strip_plurals():
    # Unlike normalize_slug, clean_token must NOT infer anything: a plural alias
    # like "pieces" is an opaque token passed through unchanged.
    assert clean_token("pieces", field="unit") == "pieces"
