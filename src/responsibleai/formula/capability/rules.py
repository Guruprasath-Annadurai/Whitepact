# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from responsibleai.formula.capability.derivation import CapabilityDerivation
from responsibleai.formula.capability.epistemic_compose import compose_epistemic
from responsibleai.formula.capability.facts import CapabilityFact
from responsibleai.formula.capability.models import CapabilityKind
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
    DIRECT_EXTRACTION = "DIRECT_EXTRACTION"
    COMPOSE_VIA_CALL = "COMPOSE_VIA_CALL"
    CREDENTIAL_UNLOCK = "CREDENTIAL_UNLOCK"
    INFORMATION_REVEALS = "INFORMATION_REVEALS"
    MULTI_AGENT_RELAY = "MULTI_AGENT_RELAY"


@dataclass(frozen=True, slots=True)
class RuleApplication:
    fact: CapabilityFact
    witness: CapabilityDerivation


def apply_composition_rules(
    snapshot: GraphSnapshot,
    facts_by_key: dict[tuple, CapabilityFact],
    *,
    max_path_depth: int,
    rule_budget: int,
) -> tuple[RuleApplication, ...]:
    """Apply typed composition rules once over the current fact set."""
    nodes = {n.node_id: n for n in snapshot.nodes}
    edges_by_src: dict[str, list] = {}
    for e in snapshot.edges:
        edges_by_src.setdefault(e.source_id, []).append(e)

    out: list[RuleApplication] = []
    applications = 0
    keys_sorted = sorted(facts_by_key.keys())

    for key in keys_sorted:
        if applications >= rule_budget:
            break
        fact = facts_by_key[key]
        if fact.action != "call":
            continue
        intermediary_id = fact.target_node_id
        im = nodes.get(intermediary_id)
        if im is None or im.kind not in _INTERMEDIARY_KINDS:
            continue
        actor = fact.actor
        for inner_key in keys_sorted:
            if applications >= rule_budget:
                break
            inner = facts_by_key[inner_key]
            if inner.actor.member_ids != (intermediary_id,):
                continue
            if inner.action == "call":
                continue
            route = (actor.member_ids[0], intermediary_id, inner.target_node_id)
            if len(route) > max_path_depth:
                continue
            composed = CapabilityFact(
                tenant_id=snapshot.tenant_id,
                actor=actor,
                action=inner.action,
                target_node_id=inner.target_node_id,
                kind=CapabilityKind.COMPOSED,
                epistemic_status=compose_epistemic(fact.epistemic_status, inner.epistemic_status),
                is_direct=False,
            )
            ck = composed.semantic_key()
            if ck in facts_by_key:
                continue
            rule = (
                RuleId.MULTI_AGENT_RELAY if im.kind == NodeKind.AGENT else RuleId.COMPOSE_VIA_CALL
            )
            witness = CapabilityDerivation(
                rule_id=rule,
                output_semantic_key=ck,
                prerequisite_keys=(fact.semantic_key(), inner.semantic_key()),
                graph_node_ids=route,
                graph_edge_ids=(),
                epistemic_status=composed.epistemic_status,
                derivation_depth=len(route) - 1,
                route_node_ids=route,
            )
            out.append(RuleApplication(composed, witness))
            applications += 1

    for edge in sorted(snapshot.edges, key=lambda e: e.edge_id):
        if applications >= rule_budget:
            break
        if edge.kind == EdgeKind.REVEALS:
            apps = _information_reveals(snapshot, edge, facts_by_key, nodes, max_path_depth)
            for app in apps:
                if applications >= rule_budget:
                    break
                if app.fact.semantic_key() not in facts_by_key:
                    out.append(app)
                    applications += 1
        if edge.kind == EdgeKind.REQUIRES:
            cred_app = _credential_unlock(snapshot, edge, facts_by_key, nodes, max_path_depth)
            if cred_app is not None and cred_app.fact.semantic_key() not in facts_by_key:
                out.append(cred_app)
                applications += 1

    return tuple(out)


def _information_reveals(
    snapshot: GraphSnapshot,
    edge,
    facts_by_key: dict,
    nodes: dict,
    max_path_depth: int,
) -> list[RuleApplication]:
    """READ on source + REVEALS -> unlock read on target information node."""
    out: list[RuleApplication] = []
    for key in sorted(facts_by_key.keys()):
        fact = facts_by_key[key]
        if fact.action != "read" or fact.target_node_id != edge.source_id:
            continue
        tgt = nodes.get(edge.target_id)
        if tgt is None:
            continue
        route = (fact.actor.member_ids[0], edge.source_id, edge.target_id)
        if len(route) > max_path_depth:
            continue
        derived = CapabilityFact(
            tenant_id=snapshot.tenant_id,
            actor=fact.actor,
            action="read",
            target_node_id=edge.target_id,
            kind=CapabilityKind.INFORMATION_DERIVED,
            epistemic_status=compose_epistemic(fact.epistemic_status, edge.epistemic_status),
            is_direct=False,
        )
        witness = CapabilityDerivation(
            rule_id=RuleId.INFORMATION_REVEALS,
            output_semantic_key=derived.semantic_key(),
            prerequisite_keys=(fact.semantic_key(),),
            graph_node_ids=route,
            graph_edge_ids=(edge.edge_id,),
            epistemic_status=derived.epistemic_status,
            derivation_depth=2,
            route_node_ids=route,
        )
        out.append(RuleApplication(derived, witness))
    return out


def _credential_unlock(
    snapshot: GraphSnapshot,
    edge,
    facts_by_key: dict,
    nodes: dict,
    max_path_depth: int,
) -> RuleApplication | None:
    """Actor READ credential + REQUIRES credential->target with grants=call."""
    grants = edge.attributes.get("grants")
    if grants != "call":
        return None
    cred = nodes.get(edge.source_id)
    if cred is None or cred.kind not in (NodeKind.CREDENTIAL, NodeKind.SECRET):
        return None
    for key in sorted(facts_by_key.keys()):
        fact = facts_by_key[key]
        if fact.action != "read" or fact.target_node_id != edge.source_id:
            continue
        route = (fact.actor.member_ids[0], edge.source_id, edge.target_id)
        if len(route) > max_path_depth:
            return None
        derived = CapabilityFact(
            tenant_id=snapshot.tenant_id,
            actor=fact.actor,
            action="call",
            target_node_id=edge.target_id,
            kind=CapabilityKind.CREDENTIAL_DERIVED,
            epistemic_status=compose_epistemic(fact.epistemic_status, edge.epistemic_status),
            is_direct=False,
        )
        witness = CapabilityDerivation(
            rule_id=RuleId.CREDENTIAL_UNLOCK,
            output_semantic_key=derived.semantic_key(),
            prerequisite_keys=(fact.semantic_key(),),
            graph_node_ids=route,
            graph_edge_ids=(edge.edge_id,),
            epistemic_status=derived.epistemic_status,
            derivation_depth=2,
            route_node_ids=route,
        )
        return RuleApplication(derived, witness)
    return None
