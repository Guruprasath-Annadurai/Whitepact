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


def test_graph_snapshot_hash_stable() -> None:
    g = CanonicalAISystemGraph("t1")
    n1 = GraphNode("n1", "t1", NodeKind.AGENT)
    n2 = GraphNode("n2", "t1", NodeKind.SECRET)
    g.add_node(n1)
    g.add_node(n2)
    e = GraphEdge("e1", "t1", EdgeKind.REVEALS, "n2", "n1")
    g.add_edge(e)
    s1 = g.freeze()
    s2 = g.freeze()
    assert s1.content_hash != s2.content_hash
    assert canonical_sha256({"a": 1}) == canonical_sha256({"a": 1})


def test_cross_tenant_node_rejected() -> None:
    g = CanonicalAISystemGraph("t1")
    with pytest.raises(CrossTenantReference):
        g.add_node(GraphNode("n2", "t2", NodeKind.API))


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


def test_state_path_semantics() -> None:
    from responsibleai.formula.trace.trace import FormulaTrace

    ts = datetime(2026, 1, 1, tzinfo=UTC)
    ev_ok = FormulaTraceEvent(
        "e1",
        "t1",
        "s",
        "a",
        "r",
        ts,
        1,
        "p",
        ("g1",),
        (),
        TransitionClass.DETERMINISTIC,
        "a",
        "b",
    )
    ev_bad = FormulaTraceEvent(
        "e2",
        "t1",
        "s",
        "a",
        "r",
        ts,
        1,
        "p",
        (),
        (),
        TransitionClass.DETERMINISTIC,
        "a",
        "b",
    )
    t_auth = FormulaTrace("t1", (ev_ok,))
    t_unauth = FormulaTrace("t1", (ev_bad,))
    assert StatePathSemantics.exists_authorized_path((t_auth, t_unauth), frozenset({"e1"}))
    assert not StatePathSemantics.all_paths_authorized((t_auth, t_unauth), frozenset({"e1"}))
