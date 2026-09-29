"""Tests for the dependency-free conversion graph engine.

The graph is the single source of truth for unit conversion, so these tests
target its public contract precisely: edge construction, the builder's
invariants, transitive-closure correctness, immutability, and the no-rounding
guarantee.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from meal_prep.engines.conversion_graph import (
    ConversionEdge,
    ConversionError,
    ConversionGraph,
    build_graph,
)

# ---------------------------------------------------------------------------
# ConversionEdge construction
# ---------------------------------------------------------------------------


def test_edge_accepts_valid_values():
    edge = ConversionEdge("piece", "g", 237.5)
    assert edge.source == "piece"
    assert edge.target == "g"
    assert edge.factor == 237.5


def test_edge_rejects_empty_endpoints():
    with pytest.raises(ValueError, match="non-empty"):
        ConversionEdge("", "g", 1.0)
    with pytest.raises(ValueError, match="non-empty"):
        ConversionEdge("piece", "", 1.0)


def test_edge_rejects_whitespace_only_endpoints():
    # A whitespace-only token is truthy in Python, so it must be rejected explicitly.
    with pytest.raises(ValueError, match="non-empty"):
        ConversionEdge(" ", "g", 1.0)
    with pytest.raises(ValueError, match="non-empty"):
        ConversionEdge("piece", "   ", 1.0)


def test_edge_rejects_self_loop():
    with pytest.raises(ValueError, match="self-reference"):
        ConversionEdge("x", "x", 1.0)


@pytest.mark.parametrize(
    "factor", [0.0, -1.0, float("inf"), float("-inf"), float("nan")]
)
def test_edge_rejects_non_positive_or_non_finite_factor(factor):
    with pytest.raises(ValueError, match="positive finite"):
        ConversionEdge("x", "y", factor)


@pytest.mark.parametrize("factor", [True, False])
def test_edge_rejects_bool_factor(factor):
    # ``bool`` is an ``int`` subclass; YAML ``factor: yes`` decodes to it. It must
    # be rejected rather than silently becoming 1.0 / 0.0.
    with pytest.raises(ValueError, match="positive finite"):
        ConversionEdge("x", "y", factor)


def test_edge_is_frozen():
    edge = ConversionEdge("a", "b", 1.0)
    with pytest.raises(Exception):
        edge.factor = 2.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# build_graph per-edge validation (self-contained builder)
# ---------------------------------------------------------------------------


def _raw(source: str, target: str, factor: float):
    """A stand-in exposing source/target/factor but bypassing ConversionEdge validation."""
    return SimpleNamespace(source=source, target=target, factor=factor)


def test_build_graph_revalidates_per_edge():
    with pytest.raises(ValueError, match="self-reference"):
        build_graph([_raw("a", "a", 1.0)])
    with pytest.raises(ValueError, match="positive finite"):
        build_graph([_raw("a", "b", 0.0)])
    with pytest.raises(ValueError, match="non-empty"):
        build_graph([_raw("", "b", 1.0)])
    with pytest.raises(ValueError, match="non-empty"):
        build_graph([_raw("a", "   ", 1.0)])
    with pytest.raises(ValueError, match="positive finite"):
        build_graph([_raw("a", "b", True)])


# ---------------------------------------------------------------------------
# build_graph structural invariants
# ---------------------------------------------------------------------------


def test_duplicate_edge_is_rejected():
    with pytest.raises(ValueError, match="redefines 'a' -> 'b'"):
        build_graph([ConversionEdge("a", "b", 2.0), ConversionEdge("a", "b", 3.0)])


def test_redundant_identical_duplicate_is_rejected():
    # Re-adding the identical edge is a no-op, so it is reported, not tolerated.
    with pytest.raises(ValueError, match="redefines"):
        build_graph([ConversionEdge("a", "b", 2.0), ConversionEdge("a", "b", 2.0)])


def test_reverse_edge_is_rejected():
    with pytest.raises(ValueError, match="defines both 'b' -> 'a' and 'a' -> 'b'"):
        build_graph([ConversionEdge("a", "b", 2.0), ConversionEdge("b", "a", 0.5)])


def test_three_node_cycle_is_rejected():
    with pytest.raises(ValueError, match="conversion cycle"):
        build_graph(
            [
                ConversionEdge("a", "b", 2.0),
                ConversionEdge("b", "c", 3.0),
                ConversionEdge("c", "a", 4.0),
            ]
        )


def test_undirected_diamond_cycle_is_rejected():
    # A diamond (a -> b, b -> c, a -> c) is acyclic in the *directed* sense, but
    # it gives ``c`` two conflicting values (authored shortcut vs derived path),
    # so it must be rejected by the undirected cycle check.
    with pytest.raises(ValueError, match="conversion cycle"):
        build_graph(
            [
                ConversionEdge("a", "b", 2.0),
                ConversionEdge("b", "c", 3.0),
                ConversionEdge("a", "c", 7.0),
            ]
        )


def test_self_loop_is_rejected_by_builder():
    with pytest.raises(ValueError, match="self-reference"):
        build_graph([ConversionEdge("a", "b", 1.0), _raw("b", "b", 1.0)])


# ---------------------------------------------------------------------------
# Transitive closure correctness
# ---------------------------------------------------------------------------


def test_empty_graph():
    graph = build_graph([])
    assert graph.units == frozenset()
    assert graph.factor("a", "b") is None
    assert graph.can_convert("a", "b") is False
    with pytest.raises(ConversionError):
        graph.convert(1.0, "a", "b")


def test_single_edge_and_derived_reverse():
    graph = build_graph([ConversionEdge("piece", "g", 237.5)])
    assert graph.convert(2, "piece", "g") == 475.0
    assert graph.convert(475.0, "g", "piece") == pytest.approx(2.0)
    # identity is implicit, no edge needed
    assert graph.convert(5.0, "g", "g") == 5.0


def test_transitive_chain():
    graph = build_graph(
        [
            ConversionEdge("package", "piece", 4.0),
            ConversionEdge("piece", "g", 237.5),
        ]
    )
    # package -> g via piece
    assert graph.convert(1, "package", "g") == 950.0
    # reverse transitive: g -> package
    assert graph.convert(950.0, "g", "package") == pytest.approx(1.0)
    # intermediate hop
    assert graph.factor("package", "piece") == 4.0
    assert graph.factor("piece", "g") == 237.5


def test_disconnected_components_do_not_cross():
    graph = build_graph(
        [
            ConversionEdge("a", "b", 2.0),
            ConversionEdge("c", "d", 3.0),
        ]
    )
    assert graph.can_convert("a", "b") is True
    assert graph.can_convert("c", "d") is True
    assert graph.can_convert("a", "c") is False
    assert graph.factor("a", "c") is None


def test_units_is_frozenset_of_all_tokens():
    graph = build_graph([ConversionEdge("a", "b", 2.0), ConversionEdge("b", "c", 3.0)])
    assert graph.units == frozenset({"a", "b", "c"})


def test_reachable_includes_source():
    graph = build_graph([ConversionEdge("a", "b", 2.0), ConversionEdge("b", "c", 3.0)])
    assert graph.reachable("a") == frozenset({"a", "b", "c"})
    assert graph.reachable("b") == frozenset({"a", "b", "c"})
    assert graph.reachable("c") == frozenset({"a", "b", "c"})


# ---------------------------------------------------------------------------
# convert() semantics
# ---------------------------------------------------------------------------


def test_convert_does_not_round():
    graph = build_graph([ConversionEdge("a", "b", 3.0)])
    raw = graph.convert(1.0, "b", "a")  # reverse edge: 1/3
    assert raw == 1.0 / 3.0
    assert raw != round(1.0 / 3.0, 6)


def test_convert_unreachable_raises_conversion_error():
    graph = build_graph([ConversionEdge("a", "b", 2.0)])
    with pytest.raises(ConversionError, match="No conversion path"):
        graph.convert(1.0, "a", "zzz")


def test_convert_zero_amount_is_zero():
    graph = build_graph([ConversionEdge("a", "b", 2.0)])
    assert graph.convert(0.0, "a", "b") == 0.0


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------


def test_factors_view_is_read_only():
    graph = build_graph([ConversionEdge("a", "b", 2.0)])
    with pytest.raises(TypeError):
        graph.factors[("a", "b")] = 999.0  # type: ignore[index]


def test_graph_rejects_mutation_of_units():
    graph = build_graph([ConversionEdge("a", "b", 2.0)])
    assert isinstance(graph.units, frozenset)
    with pytest.raises(AttributeError):
        graph.units.add("c")  # type: ignore[attr-defined]


def test_conversion_graph_is_constructible_and_read_only():
    graph = build_graph(
        [ConversionEdge("bag", "piece", 4.0), ConversionEdge("piece", "g", 237.5)]
    )
    assert isinstance(graph, ConversionGraph)
    assert graph.convert(1, "bag", "g") == 950.0
