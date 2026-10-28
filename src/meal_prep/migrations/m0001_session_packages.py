"""Migration 1: session ingredient lines gain ``aisle`` and ``package``.

Lines frozen before the session ingredient list (#152) carry only id, name,
grams and cost. This fills the aisle and the retail package (product title,
authored size, packages per batch) from the current ingredient data. That
is fair for sessions this young: today's values are what they would have
frozen. A line whose ingredient no longer exists is left as it is (the list
shows it last, in grams).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from meal_prep.adapters._yaml import read_yaml, write_yaml_atomic
from meal_prep.adapters.sessions import session_files
from meal_prep.models.library import Library

logger = logging.getLogger("meal_prep.server.migrations")


def _fill(line: dict[str, Any], library: Library) -> bool:
    if "aisle" in line and "package" in line:
        return False
    ingredient = library.ingredients.get(str(line.get("ingredient")))
    if ingredient is None:
        logger.warning("no ingredient '%s': line left as is", line.get("ingredient"))
        return False
    line.setdefault("aisle", ingredient.aisle.value)
    line.setdefault(
        "package",
        {
            "product": ingredient.product,
            "amount": ingredient.package_amount,
            "unit": ingredient.package_unit,
            "per_batch": float(line["grams"]) / ingredient.package_weight_g,
        },
    )
    return True


def apply(diary_dir: Path, library: Library) -> int:
    changed = 0
    for path in session_files(diary_dir / "sessions"):
        data = read_yaml(path, what="Prep session")
        touched = False
        for item in data.get("items") or []:
            for line in item.get("ingredients") or []:
                touched = _fill(line, library) or touched
        if touched:
            write_yaml_atomic(path, data)
            changed += 1
    return changed
