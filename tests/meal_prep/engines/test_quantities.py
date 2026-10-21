"""Tests for authored quantity parsing (``engines/quantities.py``).

Fractions and mixed numbers are parse-time conveniences: every accepted
form must come out as the exact ``float`` the arithmetic needs.
"""

from __future__ import annotations

import pytest

from meal_prep.engines.quantities import parse_quantity


def test_parse_plain_decimal():
    assert parse_quantity("1.5") == 1.5


def test_parse_whole_number():
    assert parse_quantity("2") == 2.0


def test_parse_fraction_is_exact():
    assert parse_quantity("2/3") * 120 == 80.0
    assert parse_quantity("1/3") * 120 == 40.0


def test_parse_mixed_number():
    assert parse_quantity("1 1/2") == 1.5
    assert parse_quantity("2 1/2") * 2 == 5.0


def test_parse_surrounding_whitespace():
    assert parse_quantity("  1/2  ") == 0.5


def test_parse_garbage_is_rejected():
    with pytest.raises(ValueError, match="Invalid quantity 'abc'"):
        parse_quantity("abc")


def test_parse_empty_is_rejected():
    with pytest.raises(ValueError, match="Quantity is empty"):
        parse_quantity("   ")


def test_parse_zero_denominator_is_rejected():
    with pytest.raises(ValueError, match="Invalid quantity '1/0'"):
        parse_quantity("1/0")
