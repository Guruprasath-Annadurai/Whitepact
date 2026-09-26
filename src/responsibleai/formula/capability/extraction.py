# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Direct capability extraction from explicit CAN_* graph edges."""

from __future__ import annotations

from responsibleai.formula.capability.actors import CapabilityActor
from responsibleai.formula.capability.facts import CapabilityFact
from responsibleai.formula.capability.models import CapabilityKind
from responsibleai.formula.graph.elements import GraphEdge, GraphNode
from responsibleai.formula.graph.kinds import EdgeKind, NodeKind
from responsibleai.formula.graph.snapshot import GraphSnapshot

_ACTOR_KINDS = frozenset({NodeKind.AGENT, NodeKind.HUMAN})
_COMPONENT_KINDS = frozenset(
    {
        NodeKind.TOOL,
        NodeKind.MCP_SERVER,
        NodeKind.API,
        NodeKind.SERVICE,
        NodeKind.AGENT,
    }
)

_EDGE_TO_ACTION: dict[EdgeKind, str] = {
    EdgeKind.CAN_CALL: "call",
    EdgeKind.CAN_READ: "read",
    EdgeKind.CAN_WRITE: "write",
    EdgeKind.CAN_EXECUTE: "execute",
}

_CAPABILITY_KIND_FOR_DIRECT: dict[str, CapabilityKind] = {
    "call": CapabilityKind.DIRECT_TOOL,
    "read": CapabilityKind.RESOURCE,
    "write": CapabilityKind.RESOURCE,
    "execute": CapabilityKind.DIRECT_TOOL,
}


def extract_direct_capabilities(snapshot: GraphSnapshot) -> tuple[CapabilityFact, ...]:
    """Derive direct capabilities only from CAN_CALL/READ/WRITE/EXECUTE edges."""
    nodes = {n.node_id: n for n in snapshot.nodes}
    facts: list[CapabilityFact] = []
    for edge in sorted(snapshot.edges, key=lambda e: e.edge_id):
        action = _EDGE_TO_ACTION.get(edge.kind)
        if action is None:
            continue
        src = nodes.get(edge.source_id)
        tgt = nodes.get(edge.target_id)
        if src is None or tgt is None:
            continue
        if src.kind not in _ACTOR_KINDS and src.kind not in _COMPONENT_KINDS:
            continue
        if edge.tenant_id != snapshot.tenant_id:
            continue
        actor = CapabilityActor.single(snapshot.tenant_id, src.node_id)
        kind = _CAPABILITY_KIND_FOR_DIRECT[action]
        if tgt.kind in (NodeKind.TOOL, NodeKind.MCP_SERVER, NodeKind.API, NodeKind.SERVICE):
            if action == "call":
                kind = CapabilityKind.DIRECT_TOOL
        facts.append(
            CapabilityFact(
                tenant_id=snapshot.tenant_id,
                actor=actor,
                action=action,
                target_node_id=tgt.node_id,
                kind=kind,
                epistemic_status=compose_edge_epistemic(src, edge),
                is_direct=True,
            )
        )
    return tuple(_dedupe_semantic(facts))


def compose_edge_epistemic(src: GraphNode, edge: GraphEdge):
    from responsibleai.formula.capability.epistemic_compose import compose_epistemic

    return compose_epistemic(src.epistemic_status, edge.epistemic_status)


def _dedupe_semantic(facts: list[CapabilityFact]) -> list[CapabilityFact]:
    seen: dict[tuple, CapabilityFact] = {}
    for f in facts:
        seen.setdefault(f.semantic_key(), f)
    return [seen[k] for k in sorted(seen)]
