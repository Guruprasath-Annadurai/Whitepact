# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from enum import StrEnum

from responsibleai.formula.capability.derivation import CapabilityDerivation
from responsibleai.formula.capability.epistemic_compose import compose_epistemic
from responsibleai.formula.capability.facts import CapabilityFact
from responsibleai.formula.capability.models import CapabilityKind
from responsibleai.formula.capability.routes import merge_capability_routes, route_derivation_depth
from responsibleai.formula.capability.state import CapabilityClosureState
from responsibleai.formula.graph.kinds import EdgeKind, NodeKind
from responsibleai.formula.graph.snapshot import GraphSnapshot

_INTERMEDIARY_KINDS = frozenset(
    {
        NodeKind.TOOL,
        NodeKind.MCP_SERVER,
        NodeKind.API,
        NodeKind.SERVICE,
        NodeKind.AGENT,
    }
)


class RuleId(StrEnum):
    SEED = "SEED"
    DIRECT_EXTRACTION = "DIRECT_EXTRACTION"
    COMPOSE_VIA_CALL = "COMPOSE_VIA_CALL"
    CREDENTIAL_UNLOCK = "CREDENTIAL_UNLOCK"
    INFORMATION_REVEALS = "INFORMATION_REVEALS"
    MULTI_AGENT_RELAY = "MULTI_AGENT_RELAY"
    JOINT_COALITION = "JOINT_COALITION"


def apply_composition_rules(
    snapshot: GraphSnapshot,
    state: CapabilityClosureState,
    *,
    max_path_depth: int,
    rule_budget: int,
) -> int:
    """Apply typed composition rules once; return successful witness productions."""
    nodes = {n.node_id: n for n in snapshot.nodes}
    produced = 0
    keys_sorted = sorted(state.facts_by_key.keys())

    for key in keys_sorted:
        if produced >= rule_budget:
            state.budget_truncated = True
            break
        fact = state.facts_by_key[key]
        if fact.action != "call":
            continue
        intermediary_id = fact.target_node_id
        im = nodes.get(intermediary_id)
        if im is None or im.kind not in _INTERMEDIARY_KINDS:
            continue
        actor = fact.actor
        outer_route = state.best_route(key)
        for inner_key in keys_sorted:
            if produced >= rule_budget:
                state.budget_truncated = True
                break
            inner = state.facts_by_key[inner_key]
            if inner.actor.member_ids != (intermediary_id,):
                continue
            if inner.action == "call":
                continue
            inner_route = state.best_route(inner_key)
            route = merge_capability_routes(outer_route, inner_route)
            depth = route_derivation_depth(route)
            if depth > max_path_depth:
                state.frontier_blocked = True
                if not any("max_path_depth exhausted" in n for n in state.truncation_notes):
                    state.truncation_notes.append(
                        "max_path_depth exhausted while a valid capability frontier remained"
                    )
                continue
            epistemic = compose_epistemic(
                fact.epistemic_status,
                inner.epistemic_status,
                im.epistemic_status,
            )
            composed = CapabilityFact(
                tenant_id=snapshot.tenant_id,
                actor=actor,
                action=inner.action,
                target_node_id=inner.target_node_id,
                kind=CapabilityKind.COMPOSED,
                epistemic_status=epistemic,
                is_direct=False,
            )
            ck = composed.semantic_key()
            rule = (
                RuleId.MULTI_AGENT_RELAY if im.kind == NodeKind.AGENT else RuleId.COMPOSE_VIA_CALL
            )
            witness = CapabilityDerivation(
                rule_id=rule,
                output_semantic_key=ck,
                prerequisite_keys=(fact.semantic_key(), inner.semantic_key()),
                graph_node_ids=route,
                graph_edge_ids=(),
                epistemic_status=epistemic,
                derivation_depth=depth,
                route_node_ids=route,
            )
            witness_added, _ = state.add_witness(composed, witness, is_direct=False)
            if witness_added:
                produced += 1

    for edge in sorted(snapshot.edges, key=lambda e: e.edge_id):
        if produced >= rule_budget:
            state.budget_truncated = True
            break
        if edge.kind == EdgeKind.REVEALS:
            produced += _information_reveals(
                snapshot, edge, state, nodes, max_path_depth, rule_budget - produced
            )
        if edge.kind == EdgeKind.REQUIRES:
            if produced >= rule_budget:
                state.budget_truncated = True
                break
            produced += _credential_unlock(snapshot, edge, state, nodes, max_path_depth)

    return produced


def _information_reveals(
    snapshot: GraphSnapshot,
    edge,
    state: CapabilityClosureState,
    nodes: dict,
    max_path_depth: int,
    remaining_budget: int,
) -> int:
    produced = 0
    tgt = nodes.get(edge.target_id)
    if tgt is None:
        return 0
    for key in sorted(state.facts_by_key.keys()):
        if produced >= remaining_budget:
            state.budget_truncated = True
            break
        fact = state.facts_by_key[key]
        if fact.action != "read" or fact.target_node_id != edge.source_id:
            continue
        src_info = nodes.get(edge.source_id)
        if src_info is None:
            continue
        outer_route = state.best_route(key)
        route = merge_capability_routes(outer_route, (edge.source_id, edge.target_id))
        depth = route_derivation_depth(route)
        if depth > max_path_depth:
            state.frontier_blocked = True
            state.truncation_notes.append(
                "max_path_depth exhausted while a valid capability frontier remained"
            )
            continue
        epistemic = compose_epistemic(
            fact.epistemic_status,
            edge.epistemic_status,
            src_info.epistemic_status,
            tgt.epistemic_status,
        )
        derived = CapabilityFact(
            tenant_id=snapshot.tenant_id,
            actor=fact.actor,
            action="read",
            target_node_id=edge.target_id,
            kind=CapabilityKind.INFORMATION_DERIVED,
            epistemic_status=epistemic,
            is_direct=False,
        )
        witness = CapabilityDerivation(
            rule_id=RuleId.INFORMATION_REVEALS,
            output_semantic_key=derived.semantic_key(),
            prerequisite_keys=(fact.semantic_key(),),
            graph_node_ids=route,
            graph_edge_ids=(edge.edge_id,),
            epistemic_status=epistemic,
            derivation_depth=depth,
            route_node_ids=route,
        )
        witness_added, _ = state.add_witness(derived, witness, is_direct=False)
        if witness_added:
            produced += 1
    return produced


def _credential_unlock(
    snapshot: GraphSnapshot,
    edge,
    state: CapabilityClosureState,
    nodes: dict,
    max_path_depth: int,
) -> int:
    grants = edge.attributes.get("grants")
    if grants != "call":
        return 0
    cred = nodes.get(edge.source_id)
    tgt = nodes.get(edge.target_id)
    if cred is None or cred.kind not in (NodeKind.CREDENTIAL, NodeKind.SECRET):
        return 0
    if tgt is None:
        return 0
    produced = 0
    for key in sorted(state.facts_by_key.keys()):
        fact = state.facts_by_key[key]
        if fact.action != "read" or fact.target_node_id != edge.source_id:
            continue
        outer_route = state.best_route(key)
        route = merge_capability_routes(outer_route, (edge.source_id, edge.target_id))
        depth = route_derivation_depth(route)
        if depth > max_path_depth:
            state.frontier_blocked = True
            state.truncation_notes.append(
                "max_path_depth exhausted while a valid capability frontier remained"
            )
            return produced
        epistemic = compose_epistemic(
            fact.epistemic_status,
            cred.epistemic_status,
            edge.epistemic_status,
            tgt.epistemic_status,
        )
        derived = CapabilityFact(
            tenant_id=snapshot.tenant_id,
            actor=fact.actor,
            action="call",
            target_node_id=edge.target_id,
            kind=CapabilityKind.CREDENTIAL_DERIVED,
            epistemic_status=epistemic,
            is_direct=False,
        )
        witness = CapabilityDerivation(
            rule_id=RuleId.CREDENTIAL_UNLOCK,
            output_semantic_key=derived.semantic_key(),
            prerequisite_keys=(fact.semantic_key(),),
            graph_node_ids=route,
            graph_edge_ids=(edge.edge_id,),
            epistemic_status=epistemic,
            derivation_depth=depth,
            route_node_ids=route,
        )
        witness_added, _ = state.add_witness(derived, witness, is_direct=False)
        if witness_added:
            produced += 1
        return produced
    return 0
