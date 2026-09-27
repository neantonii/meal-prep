"""Architecture drift guards: dependency-direction invariants across packages."""

import ast
import inspect
import pkgutil

import meal_prep.models as models

_FORBIDDEN_MODULES = ("meal_prep.adapters", "meal_prep.services")


def test_models_package_has_no_module_level_adapter_imports():
    """Models must not import adapters (or services) at module level.

    Adapters construct models; models never reach into adapters. The only two
    permitted cross-references are the in-function lazy imports in
    ``models/ingredient.py`` marked ``TODO(services)``; those live inside method
    bodies, not at module scope, so this top-level-import check tolerates them
    while flagging any ``models -> adapters`` import statement.
    """
    for module in pkgutil.iter_modules(models.__path__):
        mod = __import__(f"meal_prep.models.{module.name}", fromlist=["x"])
        tree = ast.parse(inspect.getsource(mod))
        for node in tree.body:
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                assert not any(name == m or name.startswith(m + ".") for m in _FORBIDDEN_MODULES), (
                    f"models.{module.name} imports {name!r} at module level"
                )
