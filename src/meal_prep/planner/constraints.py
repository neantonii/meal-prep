"""CP-SAT model constraints — one function per rule.

Solver-side build-scratch only: these operate on live OR-Tools variables
and never leave the planner. ``plan.py``/``report.py`` stay OR-Tools-free.
"""

from __future__ import annotations

from collections.abc import Iterable

from ortools.sat.python import cp_model


def exactly_one_per_meal(
    model: cp_model.CpModel, meals: Iterable[Iterable[cp_model.IntVar]]
) -> None:
    """Constrain each meal to exactly one selected recipe."""
    for is_selected in meals:
        model.add_exactly_one(is_selected)
