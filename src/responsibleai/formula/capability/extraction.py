# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Direct capability extraction from explicit CAN_* graph edges."""

from __future__ import annotations

from responsibleai.formula.capability.actors import CapabilityActor
from responsibleai.formula.capability.derivation import CapabilityDerivation
from responsibleai.formula.capability.epistemic_compose import compose_epistemic
from responsibleai.formula.capability.facts import CapabilityFact
from responsibleai.formula.capability.models import CapabilityKind
from responsibleai.formula.capability.routes import route_derivation_depth
from responsibleai.formula.capability.rules import RuleId
from responsibleai.formula.capability.state import CapabilityClosureState
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


def compose_direct_epistemic(src: GraphNode, edge: GraphEdge, tgt: GraphNode):
    return compose_epistemic(src.epistemic_status, edge.epistemic_status, tgt.epistemic_status)


def extract_direct_into_state(
    snapshot: GraphSnapshot,
    state: CapabilityClosureState,
    *,
    max_path_depth: int,
) -> int:
    """Emit DIRECT_EXTRACTION witnesses; return count of new semantic facts."""
    nodes = {n.node_id: n for n in snapshot.nodes}
    new_facts = 0
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
        route = (src.node_id, tgt.node_id)
        depth = route_derivation_depth(route)
        if depth > max_path_depth:
            state.frontier_blocked = True
            state.truncation_notes.append(
                "max_path_depth exhausted while a valid capability frontier remained"
            )
            continue
        actor = CapabilityActor.single(snapshot.tenant_id, src.node_id)
        kind = _CAPABILITY_KIND_FOR_DIRECT[action]
        if tgt.kind in (NodeKind.TOOL, NodeKind.MCP_SERVER, NodeKind.API, NodeKind.SERVICE):
            if action == "call":
                kind = CapabilityKind.DIRECT_TOOL
        epistemic = compose_direct_epistemic(src, edge, tgt)
        fact = CapabilityFact(
            tenant_id=snapshot.tenant_id,
            actor=actor,
            action=action,
            target_node_id=tgt.node_id,
            kind=kind,
            epistemic_status=epistemic,
            is_direct=True,
        )
        witness = CapabilityDerivation(
            rule_id=RuleId.DIRECT_EXTRACTION,
            output_semantic_key=fact.semantic_key(),
            prerequisite_keys=(),
            graph_node_ids=route,
            graph_edge_ids=(edge.edge_id,),
            epistemic_status=epistemic,
            derivation_depth=depth,
            route_node_ids=route,
        )
        _witness_added, fact_added = state.add_witness(fact, witness, is_direct=True)
        if fact_added:
            new_facts += 1
    return new_facts
