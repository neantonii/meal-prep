"""Pure computation kernels — no domain imports.

This package contains dependency-free logic (conversion graph, and future
kernels such as the linear-programming planner). The invariant is enforced by
``test_engines_package_has_no_domain_imports``: nothing under this package may
import from anywhere else in ``meal_prep``.
"""

from meal_prep.engines.conversion_graph import (
    ConversionEdge,
    ConversionError,
    ConversionGraph,
    build_graph,
)
from meal_prep.engines.cooklang import (
    CooklangCookware,
    CooklangDocument,
    CooklangIngredient,
    COOKWARE_PATTERN,
    INGREDIENT_PATTERN,
    parse_cooklang,
)

__all__ = [
    "ConversionEdge",
    "ConversionError",
    "ConversionGraph",
    "build_graph",
    "CooklangCookware",
    "CooklangDocument",
    "CooklangIngredient",
    "COOKWARE_PATTERN",
    "INGREDIENT_PATTERN",
    "parse_cooklang",
]
