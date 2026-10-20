"""Enforcement test for the engines dependency invariant.

Nothing under ``meal_prep.engines`` may import from anywhere else in
``meal_prep`` (cited by ``engines/README.md``, ``engines/__init__.py``, and
``engines/cooklang.py``). Intra-package imports (``meal_prep.engines`` itself,
absolute or relative) and stdlib imports are allowed; everything else —
``meal_prep.models``, third-party packages, etc. — fails this test.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import meal_prep.engines


def _violations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "meal_prep.engines" or alias.name.startswith(
                    "meal_prep.engines."
                ):
                    continue
                root = alias.name.split(".")[0]
                if root not in sys.stdlib_module_names:
                    found.append(f"{path.name}:{node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            module = node.module or ""
            root = module.split(".")[0]
            if root == "meal_prep" and (
                module == "meal_prep.engines" or module.startswith("meal_prep.engines.")
            ):
                continue
            if root not in sys.stdlib_module_names:
                found.append(f"{path.name}:{node.lineno}: from {module} import ...")
    return found


def test_engines_package_has_no_domain_imports():
    engines_dir = Path(meal_prep.engines.__file__).parent
    violations: list[str] = []
    for path in sorted(engines_dir.glob("*.py")):
        violations.extend(_violations(path))
    assert not violations, (
        "meal_prep.engines must import stdlib only (plus itself); "
        f"forbidden imports: {violations}"
    )
