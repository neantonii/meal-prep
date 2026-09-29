"""Tests for the Aisle DTO (``dtos/aisle.py``).

Happy paths plus our custom validation (``normalize_slug`` on the id) only.
Pydantic's implicit field constraints are not re-tested here.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from meal_prep.dtos.aisle import Aisle


def test_aisle_valid():
    aisle = Aisle.model_validate({"id": "produce", "name": "Produce", "order": 1})
    assert aisle.id == "produce"
    assert aisle.name == "Produce"
    assert aisle.order == 1


def test_aisle_id_is_normalized_to_slug():
    assert (
        Aisle.model_validate({"id": "  Produce  ", "name": "Produce", "order": 1}).id
        == "produce"
    )


def test_aisle_id_invalid_slug_is_rejected():
    with pytest.raises(ValidationError, match="kebab-case slug"):
        Aisle.model_validate({"id": "produce_items", "name": "Produce", "order": 1})
