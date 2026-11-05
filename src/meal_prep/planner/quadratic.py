"""Convex quadratic objective terms and the breakpoints that cut them.

CP-SAT minimizes linear objectives only. A convex term ``c·x² + b·x + d``
over an integer ``x`` becomes linear through its epigraph: a new variable
``t`` with ``t >= x²`` enforced by secant cuts, then ``c·t + b·x + d`` in the
objective. Secants reproduce linear terms exactly, so only ``x²`` is cut;
the linear part only moves the vertex, which steers breakpoint placement.

This module is solver-free: the term spec and the breakpoint placement.
``meal_prep.planner.solver`` turns them into CP-SAT variables and cuts.

Breakpoints are spaced geometrically away from the vertex (gap ratio ``rho``),
which keeps the secant's relative overestimate bounded by ``(rho-1)²/(4rho)``
everywhere. Near the vertex the geometric gaps would drop below 1, so
rounding to integers leaves every integer there: a step-1 core where the
cuts are exact. ``rho`` is the smallest ratio that fits the cut budget.
"""

from __future__ import annotations

from dataclasses import dataclass

# Bisection steps on rho: plenty to land on the budget edge.
_BISECTION_STEPS = 60
# lo, hi, the centre and its two neighbours survive any rho, so a budget
# below 4 cuts cannot always be met.
_MIN_CUTS = 4


@dataclass(frozen=True, slots=True)
class ConvexQuadratic:
    """``c·x² + b·x + d`` with ``c > 0``, in objective units (cents).

    The planner's objective is in cents, so the coefficients say how many
    cents a value of ``x`` costs.
    """

    c: float
    b: float = 0.0
    d: float = 0.0

    def __post_init__(self) -> None:
        if not self.c > 0:
            raise ValueError(
                f"ConvexQuadratic needs c > 0 (got {self.c}); "
                "a linear term needs no cuts."
            )

    @classmethod
    def deviation(cls, target: float, weight: float) -> ConvexQuadratic:
        """``weight·(x - target)²``, expanded."""
        return cls(c=weight, b=-2.0 * weight * target, d=weight * target * target)

    @property
    def vertex(self) -> float:
        """The minimizer ``-b / (2c)``."""
        return -self.b / (2.0 * self.c)

    def __call__(self, x: float) -> float:
        """The exact value at ``x`` (for reporting, not the cut estimate)."""
        return self.c * x * x + self.b * x + self.d


def square_breakpoints(
    lo: int, hi: int, focus: float, max_cuts: int = 100
) -> tuple[int, ...]:
    """Sorted integer breakpoints for cutting ``x²`` on ``[lo, hi]``.

    Always includes ``lo`` and ``hi``; at most ``max_cuts + 1`` points, so
    at most ``max_cuts`` secants. Dense (every integer) near ``focus``
    clamped to the interval, geometrically sparser away from it. When the
    interval fits the budget, every integer is a breakpoint (exact).
    """
    if lo > hi:
        raise ValueError(f"Empty interval [{lo}, {hi}].")
    if max_cuts < _MIN_CUTS:
        raise ValueError(f"max_cuts must be at least {_MIN_CUTS} (got {max_cuts}).")
    if hi - lo <= max_cuts:
        return tuple(range(lo, hi + 1))
    centre = min(max(round(focus), lo), hi)
    # Any rho above the interval width leaves only lo, hi, centre, centre±1.
    feasible = float(hi - lo + 1)
    infeasible = 1.0
    for _ in range(_BISECTION_STEPS):
        mid = (feasible + infeasible) / 2.0
        if len(_geometric_points(lo, hi, centre, mid)) <= max_cuts + 1:
            feasible = mid
        else:
            infeasible = mid
    return _geometric_points(lo, hi, centre, feasible)


def _geometric_points(lo: int, hi: int, centre: int, ratio: float) -> tuple[int, ...]:
    """``centre ± ratio^k`` (k >= 0) rounded, clipped, plus lo/hi/centre."""
    points = {lo, hi, centre}
    reach = max(centre - lo, hi - centre)
    distance = 1.0
    while distance <= reach + 1:
        for point in (round(centre - distance), round(centre + distance)):
            if lo <= point <= hi:
                points.add(point)
        distance *= ratio
    return tuple(sorted(points))
