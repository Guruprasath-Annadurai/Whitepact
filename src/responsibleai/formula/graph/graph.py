# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass, field

from responsibleai.formula.errors import CrossTenantReference, InvalidGraph, UnknownNodeKind
from responsibleai.formula.graph.elements import GraphEdge, GraphNode
from responsibleai.formula.graph.kinds import NodeKind
from responsibleai.formula.graph.snapshot import GraphSnapshot, GraphVersion
from responsibleai.formula.serialization import canonical_sha256


@dataclass
class CanonicalAISystemGraph:
    """Mutable builder; publish immutable snapshots via ``freeze``."""

    tenant_id: str
    nodes: dict[str, GraphNode] = field(default_factory=dict)
    edges: dict[str, GraphEdge] = field(default_factory=dict)
    _version_counter: int = 0

    def add_node(self, node: GraphNode) -> None:
        if node.tenant_id != self.tenant_id:
            raise CrossTenantReference(
                f"node {node.node_id} tenant {node.tenant_id} != graph {self.tenant_id}"
            )
        if not isinstance(node.kind, NodeKind):
            raise UnknownNodeKind(str(node.kind))
        self.nodes[node.node_id] = node

    def add_edge(self, edge: GraphEdge) -> None:
        if edge.tenant_id != self.tenant_id:
            raise CrossTenantReference(
                f"edge {edge.edge_id} tenant {edge.tenant_id} != graph {self.tenant_id}"
            )
        if edge.source_id not in self.nodes or edge.target_id not in self.nodes:
            raise InvalidGraph("edge references missing node")
        src, tgt = self.nodes[edge.source_id], self.nodes[edge.target_id]
        if src.tenant_id != tgt.tenant_id:
            raise CrossTenantReference("edge crosses tenant between endpoints")
        self.edges[edge.edge_id] = edge

    def freeze(self) -> GraphSnapshot:
        self._version_counter += 1
        version = GraphVersion(
            tenant_id=self.tenant_id,
            version_number=self._version_counter,
        )
        ordered_nodes = tuple(_immutable_node(self.nodes[k]) for k in sorted(self.nodes))
        ordered_edges = tuple(_immutable_edge(self.edges[k]) for k in sorted(self.edges))
        digest = canonical_sha256(
            {
                "tenant_id": self.tenant_id,
                "nodes": [_node_payload(n) for n in ordered_nodes],
                "edges": [_edge_payload(e) for e in ordered_edges],
            }
        )
        return GraphSnapshot(
            version=version,
            tenant_id=self.tenant_id,
            nodes=ordered_nodes,
            edges=ordered_edges,
            content_hash=digest,
        )


def _immutable_node(n: GraphNode) -> GraphNode:
    return GraphNode.build(
        n.node_id,
        n.tenant_id,
        n.kind,
        n.attributes,
        source=n.source,
        epistemic_status=n.epistemic_status,
        created_at=n.created_at,
        updated_at=n.updated_at,
        schema_version=n.schema_version,
    )


def _immutable_edge(e: GraphEdge) -> GraphEdge:
    return GraphEdge.build(
        e.edge_id,
        e.tenant_id,
        e.kind,
        e.source_id,
        e.target_id,
        e.attributes,
        source=e.source,
        epistemic_status=e.epistemic_status,
        created_at=e.created_at,
        updated_at=e.updated_at,
        schema_version=e.schema_version,
    )


def _node_payload(n: GraphNode) -> dict[str, object]:
    return {
        "node_id": n.node_id,
        "tenant_id": n.tenant_id,
        "kind": n.kind.value,
        "attributes": list(n._attribute_pairs),
        "source": n.source,
        "epistemic_status": n.epistemic_status.value,
        "schema_version": n.schema_version,
    }


def _edge_payload(e: GraphEdge) -> dict[str, object]:
    return {
        "edge_id": e.edge_id,
        "tenant_id": e.tenant_id,
        "kind": e.kind.value,
        "source_id": e.source_id,
        "target_id": e.target_id,
        "attributes": list(e._attribute_pairs),
        "source": e.source,
        "epistemic_status": e.epistemic_status.value,
        "schema_version": e.schema_version,
    }
