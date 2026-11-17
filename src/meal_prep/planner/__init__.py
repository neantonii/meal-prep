"""The meal planner (``docs/planner.md``).

``meal_prep.planner.plan`` holds the plain input and output values,
``meal_prep.planner.templates`` the standard meal pattern, and
``meal_prep.planner.solver`` (the only module that imports OR-Tools) builds
and solves the model. Writing a plan into the diary is the services' job.
"""

from __future__ import annotations

from meal_prep.planner.plan import (
    MealSlot,
    MealTemplate,
    Option,
    Plan,
    PlannedBatch,
    Role,
    SlotPick,
    Weights,
)

__all__ = [
    "MealSlot",
    "MealTemplate",
    "Option",
    "Plan",
    "PlannedBatch",
    "Role",
    "SlotPick",
    "Weights",
]
