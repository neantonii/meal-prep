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

from pydantic import BaseModel

from meal_prep.dtos.archetypes import ArchetypesDTO
from meal_prep.dtos.ingredient import IngredientDTO
from meal_prep.dtos.log import DiaryWeekDTO
from meal_prep.dtos.meal import MealDTO
from meal_prep.dtos.recipe import RecipeDTO
from meal_prep.dtos.session import PrepSessionDTO
from meal_prep.dtos.slots import BinDTO, UnassignedDTO
from meal_prep.dtos.staples import StaplesDTO

_REPO_ROOT = Path(__file__).resolve().parents[1]

_DTOS = {
    "archetypes": ArchetypesDTO,
    "bin": BinDTO,
    "diary": DiaryWeekDTO,
    "ingredient": IngredientDTO,
    "meal": MealDTO,
    "recipe": RecipeDTO,
    "session": PrepSessionDTO,
    "staples": StaplesDTO,
    "unassigned": UnassignedDTO,
}


def _render(dto: type[BaseModel]) -> str:
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


def _undescribed(schema: dict[str, object]) -> list[str]:
    """Models and fields of ``schema`` that carry no description (#39)."""
    missing = [] if "description" in schema else ["<root>"]
    defs = schema.get("$defs", {})
    assert isinstance(defs, dict)
    nodes: dict[str, object] = {"<root>": schema, **defs}
    for name, node in nodes.items():
        assert isinstance(node, dict)
        if name != "<root>" and "enum" not in node and "description" not in node:
            missing.append(name)
        for field, prop in node.get("properties", {}).items():
            if "description" not in prop:
                missing.append(f"{name}.{field}")
    return missing


def test_every_schema_field_is_described():
    # The schemas are the authoring contract the skills read: a model or field
    # without a description leaves its rule unstated. Enums describe
    # themselves through their values.
    for name, dto in _DTOS.items():
        missing = _undescribed(dto.model_json_schema())
        assert not missing, f"{name}: no description on {missing}"
