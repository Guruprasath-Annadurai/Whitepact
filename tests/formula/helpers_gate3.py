# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from responsibleai.formula.graph.elements import GraphEdge, GraphNode
from responsibleai.formula.graph.graph import CanonicalAISystemGraph
from responsibleai.formula.graph.kinds import EdgeKind, NodeKind
from responsibleai.formula.graph.snapshot import GraphSnapshot


def build_snapshot(
    tenant: str = "t1",
    nodes: tuple[GraphNode, ...] = (),
    edges: tuple[GraphEdge, ...] = (),
) -> GraphSnapshot:
    g = CanonicalAISystemGraph(tenant)
    for n in nodes:
        g.add_node(n)
    for e in edges:
        g.add_edge(e)
    return g.freeze()


def node(nid: str, kind: NodeKind, tenant: str = "t1") -> GraphNode:
    return GraphNode.build(nid, tenant, kind)


def edge(
    eid: str,
    kind: EdgeKind,
    src: str,
    tgt: str,
    tenant: str = "t1",
    **attrs: object,
) -> GraphEdge:
    return GraphEdge.build(eid, tenant, kind, src, tgt, attrs or None)
