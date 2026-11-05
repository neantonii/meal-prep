"""Tests for convex quadratic terms: breakpoints and the CP-SAT cuts."""

from __future__ import annotations

import bisect

import pytest
from ortools.sat.python import cp_model

from meal_prep.planner.quadratic import ConvexQuadratic, square_breakpoints
from meal_prep.planner.solver import _add_quadratic


def _secant_value(points: tuple[int, ...], x: int) -> int:
    """The cut estimate of ``x²``: the secant over ``x``'s segment."""
    index = max(1, min(bisect.bisect_right(points, x), len(points) - 1))
    left, right = points[index - 1], points[index]
    return (left + right) * x - left * right


def test_deviation_expands_to_coefficients():
    q = ConvexQuadratic.deviation(2100, 0.5)
    assert q.vertex == pytest.approx(2100)
    for x in (0, 2000, 2100, 2350):
        assert q(x) == pytest.approx(0.5 * (x - 2100) ** 2)


@pytest.mark.parametrize("c", [0.0, -1.0])
def test_rejects_non_convex(c: float):
    with pytest.raises(ValueError, match="c > 0"):
        ConvexQuadratic(c=c)


@pytest.mark.parametrize(
    ("lo", "hi", "max_cuts", "expected"),
    [(1, 1, 1, (1,)), (1, 2, 1, (1, 2)), (1, 4, 3, (1, 2, 3, 4))],
)
def test_tiny_interval_fits_any_budget(
    lo: int, hi: int, max_cuts: int, expected: tuple[int, ...]
):
    assert square_breakpoints(lo, hi, focus=1.5, max_cuts=max_cuts) == expected


def test_sparse_placement_needs_four_cuts():
    with pytest.raises(ValueError, match="at least 4"):
        square_breakpoints(0, 10, focus=5.0, max_cuts=3)


def test_small_interval_cuts_every_integer():
    assert square_breakpoints(3, 10, focus=5.0) == tuple(range(3, 11))


@pytest.mark.parametrize(
    ("lo", "hi", "focus"),
    [
        (600, 4100, 2100.0),  # vertex inside
        (600, 4100, 4500.0),  # vertex past hi: one-sided spacing
        (-3000, 3000, 0.4),  # negative x, fractional vertex
    ],
)
@pytest.mark.parametrize("max_cuts", [4, 20, 100])
def test_breakpoints_fit_budget_and_bound_error(
    lo: int, hi: int, focus: float, max_cuts: int
):
    points = square_breakpoints(lo, hi, focus, max_cuts)
    assert points[0] == lo
    assert points[-1] == hi
    assert list(points) == sorted(set(points))
    assert len(points) - 1 <= max_cuts
    if max_cuts < 100:
        return
    # Full budget: step-1 core at the vertex, small relative error elsewhere.
    centre = min(max(round(focus), lo), hi)
    assert all(
        centre + step in points for step in (-5, 0, 5) if lo <= centre + step <= hi
    )
    for x in range(lo, hi + 1):
        error = _secant_value(points, x) - x * x
        assert 0 <= error <= 0.01 * (x - focus) ** 2 + 4


def test_cuts_are_exact_at_breakpoints_and_above_between():
    model = cp_model.CpModel()
    x = model.new_int_var(-100, 5000, "x")
    term = _add_quadratic(
        model, x, 0, 4000, ConvexQuadratic.deviation(2100, 1.0), name="k", max_cuts=10
    )
    probes = [*term.breakpoints, *(p + 1 for p in term.breakpoints[:-1])]
    for value in probes:
        pinned = model.clone()
        pinned.add(pinned.get_int_var_from_proto_index(x.index) == value)
        t = pinned.get_int_var_from_proto_index(term.t.index)
        pinned.minimize(t)
        solver = cp_model.CpSolver()
        assert solver.solve(pinned) == cp_model.OPTIMAL
        assert solver.value(t) == _secant_value(term.breakpoints, value)
        if value in term.breakpoints:
            assert solver.value(t) == value * value


def test_minimum_lands_on_the_vertex():
    model = cp_model.CpModel()
    x = model.new_int_var(-100, 5000, "x")
    q = ConvexQuadratic.deviation(2137, 0.01)
    term = _add_quadratic(model, x, 0, 4000, q, name="k")
    model.minimize(term.objective)
    solver = cp_model.CpSolver()
    assert solver.solve(model) == cp_model.OPTIMAL
    assert solver.value(x) == 2137
    assert solver.objective_value == pytest.approx(0.0, abs=1e-6)


def test_single_point_interval_pins_the_square():
    model = cp_model.CpModel()
    x = model.new_int_var(-100, 100, "x")
    term = _add_quadratic(model, x, 7, 7, ConvexQuadratic(c=1.0), name="k")
    model.minimize(term.objective)
    solver = cp_model.CpSolver()
    assert solver.solve(model) == cp_model.OPTIMAL
    assert solver.value(term.t) == 49


def test_bounds_are_enforced():
    model = cp_model.CpModel()
    x = model.new_int_var(-100, 5000, "x")
    model.add(x == 4500)
    _add_quadratic(model, x, 0, 4000, ConvexQuadratic(c=1.0), name="k")
    assert cp_model.CpSolver().solve(model) == cp_model.INFEASIBLE
