"""The meal planner (``docs/planner.md``).

``meal_prep.planner.plan`` holds the plain input and output values,
``meal_prep.planner.archetypes`` the standard archetypes per mealtime, and
``meal_prep.planner.solver`` (the only module that imports OR-Tools) builds
and solves the model. Writing a plan into the diary is the services' job.
"""

from __future__ import annotations

from meal_prep.planner.plan import (
    TAKEOUT,
    Archetype,
    Batch,
    Cook,
    Pin,
    Placement,
    Plan,
    Problem,
    Role,
    Slot,
    Weights,
)

__all__ = [
    "TAKEOUT",
    "Archetype",
    "Batch",
    "Cook",
    "Pin",
    "Placement",
    "Plan",
    "Problem",
    "Role",
    "Slot",
    "Weights",
]
