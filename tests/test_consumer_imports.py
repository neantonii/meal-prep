"""Enforcement test for the two-tier rule: consumers see enriched models only.

The loading machinery (``adapters`` -> ``dtos`` -> ``services``) and the
assembly root (``meal_prep.library``) build a frozen ``Library``. Consumers
(renderers, the logbook, the planner) work from enriched models and must not
reach back into that machinery. Entry points that sit on an I/O boundary (the
diary server, ``scripts/``) are deliberately not consumers: they load, save
and validate authored data.
"""

from __future__ import annotations

import ast
from pathlib import Path

import meal_prep

_SRC = Path(meal_prep.__file__).parent

CONSUMERS = (
    _SRC / "renderer.py",
    _SRC / "ingredient_cards.py",
    *sorted((_SRC / "logbook").glob("*.py")),
    *sorted((_SRC / "planner").glob("*.py")),
)

FORBIDDEN = (
    "meal_prep.adapters",
    "meal_prep.dtos",
    "meal_prep.services",
    "meal_prep.library",
)


def _forbidden_imports(source: str, name: str) -> list[str]:
    found: list[str] = []
    for node in ast.walk(ast.parse(source, filename=name)):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and not node.level:
            modules = [node.module or ""]
        else:
            continue
        for module in modules:
            if any(module == f or module.startswith(f + ".") for f in FORBIDDEN):
                found.append(f"{name}:{node.lineno}: {module}")
    return found


def test_consumers_import_no_loading_machinery():
    violations = [
        v
        for path in CONSUMERS
        for v in _forbidden_imports(path.read_text(encoding="utf-8"), path.name)
    ]
    assert not violations, (
        "consumers must use enriched models only (meal_prep.models, enums, "
        f"engines); forbidden imports: {violations}"
    )


def test_checker_flags_forbidden_imports():
    source = (
        "from meal_prep.models.recipe import Recipe\n"
        "from meal_prep.services.recipes import prepare_recipe\n"
        "import meal_prep.dtos.recipe\n"
        "if True:\n"
        "    from meal_prep.library import load_library\n"
    )
    assert _forbidden_imports(source, "x.py") == [
        "x.py:2: meal_prep.services.recipes",
        "x.py:3: meal_prep.dtos.recipe",
        "x.py:5: meal_prep.library",
    ]
