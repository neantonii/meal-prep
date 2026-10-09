"""Schema freshness test: committed schemas must match the live DTOs.

This is a drift guard, not a unit test. It regenerates each schema in memory
and diffs against the committed file. If a DTO change alters the authoring
contract, this fails; run ``python scripts/refresh_schemas.py`` and commit
the diff so the contract change is visible in review.
"""

from __future__ import annotations

import difflib
import json
from pathlib import Path

from meal_prep.dtos.ingredient import IngredientDTO
from meal_prep.dtos.log import LogWeekDTO
from meal_prep.dtos.meal import MealDTO
from meal_prep.dtos.recipe import RecipeDTO

_REPO_ROOT = Path(__file__).resolve().parents[1]

_DTOS = {
    "ingredient": IngredientDTO,
    "log": LogWeekDTO,
    "meal": MealDTO,
    "recipe": RecipeDTO,
}


def _render(
    dto: type[IngredientDTO] | type[LogWeekDTO] | type[MealDTO] | type[RecipeDTO],
) -> str:
    return json.dumps(dto.model_json_schema(), indent=2, sort_keys=True) + "\n"


def test_committed_schemas_match_dtos():
    for name, dto in _DTOS.items():
        path = _REPO_ROOT / "schemas" / f"{name}.schema.json"
        assert path.exists(), f"{path} missing — run scripts/refresh_schemas.py"
        live = _render(dto)
        committed = path.read_text(encoding="utf-8")
        if live != committed:
            diff = "".join(
                difflib.unified_diff(
                    committed.splitlines(keepends=True),
                    live.splitlines(keepends=True),
                    fromfile=f"committed {name}.schema.json",
                    tofile="live DTO schema",
                )
            )
            raise AssertionError(
                f"schemas/{name}.schema.json is stale — "
                f"run python scripts/refresh_schemas.py and commit the diff:\n{diff}"
            )
