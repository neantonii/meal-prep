"""Tests for session freezing and what a session needs on hand
(``services/sessions.py``, ``PrepSession.needs``)."""

from __future__ import annotations

import datetime
import uuid
from pathlib import Path

import pytest

from meal_prep.dtos.session import PrepSessionDTO
from meal_prep.enums import Aisle
from meal_prep.library import load_library
from meal_prep.models.library import Library
from meal_prep.services.sessions import freeze_item, prepare_session

_REPO_ROOT = Path(__file__).resolve().parents[3]
CHICKEN = "air-fried-chicken-breast"
RICE = "boiled-basmati-rice"


@pytest.fixture(scope="module")
def library() -> Library:
    return load_library(_REPO_ROOT / "data", _REPO_ROOT / "recipes")


def _session(*items) -> PrepSessionDTO:
    return PrepSessionDTO(
        id=uuid.uuid4(), date=datetime.date(2026, 11, 1), items=list(items)
    )


def test_freezing_records_aisle_and_package_per_batch(library: Library):
    recipe = library.recipes[CHICKEN]
    item = freeze_item(recipe)
    for line, source in zip(item.ingredients, recipe.ingredients, strict=True):
        assert line.aisle is source.aisle
        assert line.package is not None
        assert line.package.product == source.package.product
        assert (line.package.amount, line.package.unit) == (
            source.package.amount,
            source.package.unit,
        )
        assert line.package.per_batch == pytest.approx(
            source.grams / source.package.weight_g
        )


def test_needs_sum_batches_per_ingredient_in_walking_order(library: Library):
    chicken = freeze_item(library.recipes[CHICKEN], batches=2)
    rice = freeze_item(library.recipes[RICE])
    groups = prepare_session(_session(chicken, rice)).needs()
    aisles = [g.aisle for g in groups]
    assert aisles == sorted(aisles, key=list(Aisle).index)  # type: ignore[arg-type]
    needed = {i.ingredient_id: i for g in groups for i in g.ingredients}
    for line in chicken.ingredients:
        assert line.package is not None
        got = needed[line.ingredient]
        if line.ingredient not in {r.ingredient for r in rice.ingredients}:
            assert got.grams == pytest.approx(2 * line.grams)
            assert got.packages == pytest.approx(2 * line.package.per_batch)
            assert got.recipes == (chicken.title,)
    shared = {i.ingredient for i in chicken.ingredients} & {
        i.ingredient for i in rice.ingredients
    }
    for ingredient in shared:
        assert needed[ingredient].recipes == (chicken.title, rice.title)
    total = sum(g.cost for g in groups)
    assert total == pytest.approx(
        2 * sum(i.cost for i in chicken.ingredients)
        + sum(i.cost for i in rice.ingredients)
    )


def test_lines_from_older_files_are_listed_last_without_packages(
    library: Library,
):
    item = freeze_item(library.recipes[CHICKEN])
    old = item.model_copy(
        update={
            "ingredients": [
                line.model_copy(update={"aisle": None, "package": None})
                for line in item.ingredients
            ]
        }
    )
    other = freeze_item(library.recipes[RICE])
    groups = prepare_session(_session(old, other)).needs()
    assert groups[-1].aisle is None
    assert all(i.packages is None and i.package is None for i in groups[-1].ingredients)
    assert all(g.aisle is not None for g in groups[:-1])
