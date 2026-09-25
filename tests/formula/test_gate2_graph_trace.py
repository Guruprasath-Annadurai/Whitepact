# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from responsibleai.formula.errors import CrossTenantReference
from responsibleai.formula.graph.elements import GraphEdge, GraphNode
from responsibleai.formula.graph.graph import CanonicalAISystemGraph
from responsibleai.formula.graph.kinds import EdgeKind, NodeKind
from responsibleai.formula.serialization import canonical_sha256
from responsibleai.formula.trace.semantics import StatePathSemantics, demonstrate_exists_vs_all
from responsibleai.formula.trace.trace import FormulaTraceEvent, TransitionClass


def test_graph_snapshot_hash_stable_for_same_content() -> None:
    g1 = CanonicalAISystemGraph("t1")
    n1 = GraphNode.build("n1", "t1", NodeKind.AGENT, {"role": "a"})
    n2 = GraphNode.build("n2", "t1", NodeKind.SECRET)
    g1.add_node(n1)
    g1.add_node(n2)
    g1.add_edge(GraphEdge.build("e1", "t1", EdgeKind.REVEALS, "n2", "n1"))
    s1 = g1.freeze()
    g2 = CanonicalAISystemGraph("t1")
    g2.add_node(GraphNode.build("n1", "t1", NodeKind.AGENT, {"role": "a"}))
    g2.add_node(GraphNode.build("n2", "t1", NodeKind.SECRET))
    g2.add_edge(GraphEdge.build("e1", "t1", EdgeKind.REVEALS, "n2", "n1"))
    s2 = g2.freeze()
    assert s1.content_hash == s2.content_hash
    # Version identity is per-builder freeze sequence, not content-addressed.
    s1b = g1.freeze()
    assert s1.content_hash == s1b.content_hash
    assert s1.version.version_number != s1b.version.version_number
    assert canonical_sha256({"a": 1}) == canonical_sha256({"a": 1})


def test_snapshot_immutable_after_mutation() -> None:
    attrs = {"k": "v"}
    g = CanonicalAISystemGraph("t1")
    g.add_node(GraphNode.build("n1", "t1", NodeKind.AGENT, attrs))
    snap = g.freeze()
    attrs["k"] = "mutated"
    assert snap.nodes[0].attributes["k"] == "v"


def test_cross_tenant_node_rejected() -> None:
    g = CanonicalAISystemGraph("t1")
    with pytest.raises(CrossTenantReference):
        g.add_node(GraphNode.build("n2", "t2", NodeKind.API))


def test_exists_vs_all_paths() -> None:
    ts = datetime(2026, 1, 1, tzinfo=UTC)
    ev_ok = FormulaTraceEvent(
        "e1",
        "t1",
        "s",
        "read",
        "x",
        ts,
        1,
        "p1",
        ("g1",),
        (),
        TransitionClass.DETERMINISTIC,
        "h0",
        "h1",
    )
    ev_bad = FormulaTraceEvent(
        "e2",
        "t1",
        "s",
        "write",
        "x",
        ts,
        1,
        "p1",
        (),
        (),
        TransitionClass.DETERMINISTIC,
        "h1",
        "h2",
    )
    exists, all_ok = demonstrate_exists_vs_all(ev_ok, ev_bad, frozenset({"e1"}))
    assert exists is True
    assert all_ok is False


def test_state_path_empty_not_authorized() -> None:
    assert StatePathSemantics.exists_authorized_path((), frozenset({"e1"})) is False
    assert StatePathSemantics.all_paths_authorized((), frozenset({"e1"})) is False
