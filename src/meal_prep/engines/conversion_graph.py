"""Directed unit-conversion graph — a self-contained, immutable model.

This module is the single source of truth for converting between measurement
units within one ingredient. It is deliberately dependency-free: it imports
nothing from the rest of the codebase (no ingredients, no units registry, no
YAML, no Pydantic). Unit names are opaque string *tokens*; their real-world
meaning (grams, pieces, packages) is imposed by the caller, never by this module.

Model
-----
An *edge* ``source -> target = factor`` means "one ``source`` equals ``factor``
``target``s". Edges are directed, but each edge implies its reverse, which is
derived automatically at build time.

Invariants — enforced by :func:`build_graph`
--------------------------------------------
1. **Positive finite real factors.** Every ``factor`` must be a finite real
   number > 0. ``bool`` is rejected explicitly (it is an ``int`` subclass, and
   YAML ``yes``/``no`` decode to it).
2. **Non-empty, non-whitespace endpoints.** ``source`` and ``target`` must be
   distinct, non-empty strings with at least one non-whitespace character.
3. **At most one directed edge per ordered pair.** A second ``A -> B`` is
   rejected even when the factor is identical; the reverse ``B -> A`` is
   rejected too, because it is derived automatically.
4. **Acyclic in the undirected sense.** The *unordered* edge set must be a
   forest: an undirected cycle (which the directed acyclicity check would miss,
   e.g. the diamond ``a -> b, b -> c, a -> c``) would give ``c`` two conflicting
   values — the authored shortcut and the derived path — so it is rejected
   rather than silently keeping one.
5. **Immutable.** A built graph cannot be mutated and exposes read-only views;
   factor lookups are O(1).

These rules are the contract that everything downstream — ingredient pricing,
per-serving macros, batch weights — depends on. Keeping them here, in one
dependency-free place, is what protects their correctness from unrelated
refactoring elsewhere in the codebase.
"""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType


class ConversionError(ValueError):
    """Raised when a conversion is requested that the graph cannot express."""


def _check_edge(source: str, target: str, factor: float) -> None:
    """Validate a single edge's endpoints and factor.

    Called from both ``ConversionEdge.__post_init__`` (so a malformed edge can
    never be constructed) and ``build_graph`` (so the public builder is
    self-contained and does not trust its input to have been pre-validated).
    """
    if not source or not source.strip() or not target or not target.strip():
        raise ValueError(
            "Conversion edge endpoints must be non-empty, non-whitespace tokens."
        )
    if source == target:
        raise ValueError(
            f"Conversion self-reference '{source}' -> '{target}' is not allowed; "
            "a token is equal to itself by a factor of 1 and needs no edge."
        )
    # ``bool`` is a subclass of ``int`` and YAML ``yes``/``no`` decode to it, so
    # it must be rejected explicitly before the finite/positive check.
    if isinstance(factor, bool) or not math.isfinite(factor) or factor <= 0:
        raise ValueError(
            f"Conversion factor must be a positive finite number, got {factor!r}."
        )


@dataclass(frozen=True, slots=True)
class ConversionEdge:
    """A directed conversion edge: 1 ``source`` equals ``factor`` × ``target``.

    Frozen so a validated edge cannot be mutated after construction. The
    per-edge invariant (positive finite factor, distinct non-empty endpoints)
    is enforced here at the type boundary.
    """

    source: str
    target: str
    factor: float

    def __post_init__(self) -> None:
        _check_edge(self.source, self.target, self.factor)


class ConversionGraph:
    """Immutable transitive closure of a validated set of conversion edges."""

    __slots__ = ("_factors", "_units")

    def __init__(self, factors: Mapping[tuple[str, str], float]) -> None:
        self._factors: Mapping[tuple[str, str], float] = MappingProxyType(dict(factors))
        self._units: frozenset[str] = frozenset(
            tok for pair in self._factors for tok in pair
        )

    @property
    def factors(self) -> Mapping[tuple[str, str], float]:
        """Read-only view of every reachable ``(source, target) -> factor`` pair."""
        return self._factors

    @property
    def units(self) -> frozenset[str]:
        """All unit tokens present in the graph."""
        return self._units

    def factor(self, source: str, target: str) -> float | None:
        """Return the multiplication factor from ``source`` to ``target``, or ``None``."""
        return self._factors.get((source, target))

    def can_convert(self, source: str, target: str) -> bool:
        """Return True if a conversion path exists between ``source`` and ``target``."""
        return (source, target) in self._factors

    def reachable(self, source: str) -> frozenset[str]:
        """Return every token reachable from ``source`` (including ``source`` itself)."""
        return frozenset(to for (frm, to) in self._factors if frm == source) | {source}

    def convert(self, amount: float, source: str, target: str) -> float:
        """Convert ``amount`` from ``source`` to ``target``.

        Raises :class:`ConversionError` if no path exists. The result is the raw
        product ``amount * factor`` with no rounding — presentation is the
        caller's concern.
        """
        factor = self._factors.get((source, target))
        if factor is None:
            raise ConversionError(
                f"No conversion path exists between '{source}' and '{target}'."
            )
        return amount * factor


def build_graph(edges: Sequence[ConversionEdge]) -> ConversionGraph:
    """Validate a directed edge set and return its immutable transitive closure.

    Raises :class:`ValueError` on any invariant violation (see the module
    docstring). Reciprocals are added only after validation: validating the
    augmented graph would make every edge a two-cycle, which is why the
    duplicate and cycle checks all run on the authored set first.
    """
    adjacency: dict[str, dict[str, float]] = {}
    seen: set[tuple[str, str]] = set()

    for edge in edges:
        u, v, factor = edge.source, edge.target, edge.factor
        # Validate per-edge invariants here too, so build_graph is a
        # self-contained public builder that does not trust its inputs to have
        # been pre-validated by ConversionEdge.
        _check_edge(u, v, factor)

        if (u, v) in seen:
            raise ValueError(
                f"'{u}' -> '{v}' = {factor} redefines '{u}' -> '{v}', which is already "
                f"present. Re-adding an edge is a no-op; remove the redundant definition."
            )
        if (v, u) in seen:
            raise ValueError(
                f"'{u}' -> '{v}' = {factor} defines both '{u}' -> '{v}' and '{v}' -> '{u}', "
                f"which is already present. Authoring both directions of one conversion is "
                f"redundant; the reverse is derived automatically."
            )

        seen.add((u, v))
        adjacency.setdefault(u, {})[v] = factor
        adjacency.setdefault(v, {})

    _reject_cycles(seen)

    for u, neighbors in list(adjacency.items()):
        for v, factor in list(neighbors.items()):
            adjacency[v].setdefault(u, 1.0 / factor)

    closure: dict[tuple[str, str], float] = {}
    for source in adjacency:
        visited = {source: 1.0}
        queue = deque([source])
        while queue:
            node = queue.popleft()
            for neighbor, edge_factor in adjacency[node].items():
                if neighbor not in visited:
                    visited[neighbor] = visited[node] * edge_factor
                    queue.append(neighbor)
        for target, factor in visited.items():
            closure[(source, target)] = factor

    return ConversionGraph(closure)


def _reject_cycles(edges: set[tuple[str, str]]) -> None:
    """Raise if the *unordered* edge set contains a cycle (union-find).

    The directed graph is always acyclic when there is at most one edge per
    ordered pair, but an undirected cycle (e.g. ``a -> b, b -> c, a -> c``) is a
    genuine error: it gives one token two conflicting values — the authored
    shortcut and the derived path. Union-find over unordered pairs rejects such
    cycles.
    """
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for u, v in edges:
        if u not in parent:
            parent[u] = u
        if v not in parent:
            parent[v] = v

        ru, rv = find(u), find(v)
        if ru == rv:
            raise ValueError(
                f"Detected a conversion cycle: adding '{u}' -> '{v}' would create a "
                f"loop in the undirected conversion graph."
            )
        parent[ru] = rv
