"""Directed unit-conversion graph — a self-contained, immutable model.

This module is the single source of truth for converting between measurement
units within one ingredient. It is deliberately dependency-free: it imports
nothing from the rest of the codebase (no ingredients, no units registry, no
YAML, no Pydantic). Unit names are opaque string *tokens*; their real-world
meaning (grams, pieces, packaging containers) is imposed by the caller, never
by this module.

Model
-----
An *edge* ``source -> target = factor`` means "one ``source`` equals ``factor``
``target``s". Edges are directed, but each edge implies its reverse, which is
derived automatically at build time.

Invariants — enforced by :func:`build_graph`
--------------------------------------------
1. **Positive finite factors.** Every ``factor`` must be a finite number > 0.
2. **No self-loop.** ``source != target``; a token is equal to itself by a
   factor of exactly 1, which needs no edge.
3. **One edge per pair.** Each unordered pair of tokens may be connected in at
   most one direction. Re-adding a directed edge, or adding its reverse, is
   redundant (the reverse is derived) and is rejected rather than silently
   merged. This is what keeps contradictory authoring from producing silently
   wrong numbers.
4. **Acyclic.** The directed edge set contains no cycle; otherwise some token
   would be equal to itself by a non-unit factor.
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
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType


class ConversionError(ValueError):
    """Raised when a conversion is requested that the graph cannot express."""


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
        if not self.source or not self.target:
            raise ValueError("Conversion edge endpoints must be non-empty tokens.")
        if self.source == self.target:
            raise ValueError(
                f"Conversion self-reference '{self.source}' -> '{self.target}' is not allowed; "
                "a token is equal to itself by a factor of 1 and needs no edge."
            )
        if not math.isfinite(self.factor) or self.factor <= 0:
            raise ValueError(
                f"Conversion factor must be a positive finite number, got {self.factor!r}."
            )


class ConversionGraph:
    """Immutable transitive closure of a validated set of conversion edges."""

    __slots__ = ("_factors", "_units")

    def __init__(self, factors: Mapping[tuple[str, str], float]) -> None:
        self._factors: Mapping[tuple[str, str], float] = MappingProxyType(dict(factors))
        self._units: frozenset[str] = frozenset(tok for pair in self._factors for tok in pair)

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
    duplicate, self-loop and cycle checks all run on the directed set first.
    """
    adjacency: dict[str, dict[str, float]] = {}
    seen: dict[tuple[str, str], float] = {}

    for edge in edges:
        u, v, factor = edge.source, edge.target, edge.factor
        # Per-edge validity (positive finite factor, distinct endpoints) is
        # already guaranteed by ConversionEdge.__post_init__.

        if (u, v) in seen:
            prev = seen[(u, v)]
            raise ValueError(
                f"'{u}' -> '{v}' = {factor} redefines '{u}' -> '{v}' = {prev}, which is already "
                f"present. Re-adding an edge is a no-op; remove the redundant definition."
            )
        if (v, u) in seen:
            prev = seen[(v, u)]
            raise ValueError(
                f"'{u}' -> '{v}' = {factor} defines both '{u}' -> '{v}' and '{v}' -> '{u}' = "
                f"{prev}. Authoring both directions of one conversion is redundant; the reverse is "
                f"derived automatically."
            )

        seen[(u, v)] = factor
        adjacency.setdefault(u, {})[v] = factor
        adjacency.setdefault(v, {})

    _reject_cycles(adjacency)

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


def _reject_cycles(adjacency: Mapping[str, Mapping[str, float]]) -> None:
    """Raise if the directed adjacency contains a cycle (iterative DFS, three-colour marking)."""
    WHITE, GREY, BLACK = 0, 1, 2
    colour: dict[str, int] = {}

    for start in adjacency:
        if colour.get(start, WHITE) != WHITE:
            continue
        colour[start] = GREY
        path: list[str] = [start]
        stack: list[tuple[str, Iterator[str]]] = [(start, iter(adjacency.get(start, {})))]
        while stack:
            node, children = stack[-1]
            advanced = False
            for child in children:
                state = colour.get(child, WHITE)
                if state == GREY:
                    raise ValueError(
                        f"Detected a conversion cycle: "
                        f"{' -> '.join(path[path.index(child):] + [child])}."
                    )
                if state == WHITE:
                    colour[child] = GREY
                    path.append(child)
                    stack.append((child, iter(adjacency.get(child, {}))))
                    advanced = True
                    break
            if not advanced:
                colour[node] = BLACK
                stack.pop()
                path.pop()
