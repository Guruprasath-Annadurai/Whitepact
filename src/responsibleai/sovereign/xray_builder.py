# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Repository-backed authority topology for Sovereign X-Ray."""

from __future__ import annotations

from responsibleai.governance.delegation_graph import DelegationGraphNode
from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.graph import (
    AuthorityGraph,
    EdgeDerivation,
    GraphEdge,
    GraphEdgeKind,
    GraphNode,
    GraphNodeKind,
    GraphProvenance,
    GraphQueryBudget,
)
from responsibleai.sovereign.sources import SovereignCanonicalStore


def _stable_sort_nodes(nodes: list[GraphNode]) -> list[GraphNode]:
    return sorted(nodes, key=lambda n: n.node_id)


def _stable_sort_edges(edges: list[GraphEdge]) -> list[GraphEdge]:
    return sorted(edges, key=lambda e: e.edge_id)


async def build_repository_xray(
    store: SovereignCanonicalStore,
    ctx: SovereignContext,
    *,
    budget: GraphQueryBudget | None = None,
    evidence_limit: int = 25,
) -> AuthorityGraph:
    budget = budget or GraphQueryBudget()
    org_id = ctx.organization_id
    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []
    truncated = False
    truncation_reason: str | None = None

    def add_node(node: GraphNode) -> bool:
        if len(nodes) >= budget.max_nodes:
            return False
        nodes[node.node_id] = node
        return True

    def add_edge(edge: GraphEdge) -> bool:
        if len(edges) >= budget.max_edges:
            return False
        edges.append(edge)
        return True

    org = await store.orgs.get_org(org_id)
    org_label = org.name if org is not None else org_id
    if not add_node(
        GraphNode(
            node_id=f"org:{org_id}",
            kind=GraphNodeKind.ORGANIZATION,
            label=org_label,
            organization_id=org_id,
            metadata={"source": "org_repository.get_org"},
        )
    ):
        truncated = True
        truncation_reason = "node budget exceeded at organization"
    else:
        policy_version = await store.policies.get_policy_version(org_id)
        policy_node_id = f"policy:{org_id}:v{policy_version}"
        if add_node(
            GraphNode(
                node_id=policy_node_id,
                kind=GraphNodeKind.POLICY,
                label=f"policy v{policy_version}",
                organization_id=org_id,
                metadata={"policy_version": policy_version},
            )
        ):
            add_edge(
                GraphEdge(
                    edge_id=f"edge:governed:{org_id}",
                    kind=GraphEdgeKind.GOVERNED_BY,
                    from_node_id=f"org:{org_id}",
                    to_node_id=policy_node_id,
                    provenance=GraphProvenance(
                        source="policy_repository.get_policy_version",
                        derivation=EdgeDerivation.DIRECT,
                        explanation="Organization policy version from canonical policy store",
                        fact_refs=[f"policy_version:{policy_version}"],
                    ),
                )
            )

        ceiling = await store.ceilings.get(org_id)
        if ceiling is not None:
            cap_node = f"ceiling:{org_id}"
            if add_node(
                GraphNode(
                    node_id=cap_node,
                    kind=GraphNodeKind.CAPABILITY,
                    label="org_authority_ceiling",
                    organization_id=org_id,
                    metadata={
                        "max_delegation_depth": ceiling.max_delegation_depth,
                        "allowed_action_types": ceiling.allowed_action_types,
                    },
                )
            ):
                add_edge(
                    GraphEdge(
                        edge_id=f"edge:ceiling:{org_id}",
                        kind=GraphEdgeKind.GOVERNED_BY,
                        from_node_id=f"org:{org_id}",
                        to_node_id=cap_node,
                        provenance=GraphProvenance(
                            source="org_authority_ceiling_repository.get",
                            derivation=EdgeDerivation.DIRECT,
                            explanation="Structural org authority ceiling envelope",
                        ),
                    )
                )

        graph = await store.delegations.get_org_graph(org_id)
        seen_edges: set[str] = set()

        def walk(node: DelegationGraphNode, depth: int, lineage: set[str]) -> None:
            nonlocal truncated, truncation_reason
            if depth > budget.max_depth:
                truncated = True
                truncation_reason = "max_depth exceeded in delegation forest"
                return
            if node.identity_id in lineage:
                truncated = True
                truncation_reason = f"cycle detected at identity {node.identity_id}"
                return
            lineage = set(lineage)
            lineage.add(node.identity_id)
            ident_node = f"identity:{node.identity_id}"
            if not add_node(
                GraphNode(
                    node_id=ident_node,
                    kind=GraphNodeKind.AGENT,
                    label=node.identity_id,
                    organization_id=org_id,
                    metadata={"active": node.is_active()},
                )
            ):
                truncated = True
                return
            add_edge(
                GraphEdge(
                    edge_id=f"edge:member:{node.identity_id}",
                    kind=GraphEdgeKind.MEMBER_OF,
                    from_node_id=ident_node,
                    to_node_id=f"org:{org_id}",
                    provenance=GraphProvenance(
                        source="delegation_repository.get_org_graph",
                        derivation=EdgeDerivation.DIRECT,
                        explanation="Identity appears in org delegation graph",
                    ),
                )
            )
            if node.delegation is not None:
                del_id = node.delegation.delegation_id
                del_node = f"delegation:{del_id}"
                if add_node(
                    GraphNode(
                        node_id=del_node,
                        kind=GraphNodeKind.DELEGATION,
                        label=del_id,
                        organization_id=org_id,
                        metadata={"is_active": node.delegation.is_active()},
                    )
                ):
                    parent = node.delegation.from_identity_id
                    derivation = EdgeDerivation.DELEGATED if parent else EdgeDerivation.DIRECT
                    from_id = f"identity:{parent}" if parent else f"org:{org_id}"
                    edge_key = f"deleg:{del_id}"
                    if edge_key not in seen_edges:
                        seen_edges.add(edge_key)
                        add_edge(
                            GraphEdge(
                                edge_id=f"edge:delegated:{del_id}",
                                kind=GraphEdgeKind.DELEGATED_TO,
                                from_node_id=from_id,
                                to_node_id=ident_node,
                                provenance=GraphProvenance(
                                    source="governance_delegations",
                                    derivation=derivation,
                                    explanation="Delegation grant row",
                                    fact_refs=[f"delegation_id:{del_id}"],
                                ),
                            )
                        )
                    for action in sorted(node.delegation.granted_action_types):
                        cap_id = f"capability:{action}"
                        if add_node(
                            GraphNode(
                                node_id=cap_id,
                                kind=GraphNodeKind.CAPABILITY,
                                label=action,
                                organization_id=org_id,
                            )
                        ):
                            add_edge(
                                GraphEdge(
                                    edge_id=f"edge:can_call:{node.identity_id}:{action}",
                                    kind=GraphEdgeKind.CAN_CALL,
                                    from_node_id=ident_node,
                                    to_node_id=cap_id,
                                    provenance=GraphProvenance(
                                        source="delegation.granted_action_types",
                                        derivation=EdgeDerivation.DIRECT
                                        if depth == 0
                                        else EdgeDerivation.TRANSITIVE,
                                        explanation="Granted action type on active delegation chain",
                                        fact_refs=[f"delegation_id:{del_id}"],
                                    ),
                                )
                            )
                        for req in sorted(node.delegation.require_approval_for):
                            if action == req or req == "*":
                                add_edge(
                                    GraphEdge(
                                        edge_id=f"edge:req_approval:{del_id}:{req}",
                                        kind=GraphEdgeKind.REQUIRES_APPROVAL,
                                        from_node_id=ident_node,
                                        to_node_id=cap_id,
                                        provenance=GraphProvenance(
                                            source="delegation.require_approval_for",
                                            derivation=EdgeDerivation.DIRECT,
                                            explanation="Delegation marks action as approval-gated",
                                            fact_refs=[f"delegation_id:{del_id}"],
                                        ),
                                    )
                                )
            for child in node.children:
                walk(child, depth + 1, lineage)

        for root in graph.roots:
            walk(root, 0, set())

        evidence_rows = await store.evidence.list_for_org(org_id, limit=evidence_limit)
        for ev in evidence_rows:
            ev_node = f"evidence:{ev.evidence_id}"
            if not add_node(
                GraphNode(
                    node_id=ev_node,
                    kind=GraphNodeKind.EVIDENCE,
                    label=ev.evidence_id,
                    organization_id=org_id,
                    metadata={
                        "decision": ev.decision,
                        "action_type": ev.action_type,
                        "evaluated_at": ev.evaluated_at,
                    },
                )
            ):
                truncated = True
                break
            actor = ev.identity_id or ev.agent_id
            if actor:
                actor_node = f"identity:{actor}"
                if actor_node in nodes:
                    add_edge(
                        GraphEdge(
                            edge_id=f"edge:evidence:{ev.evidence_id}",
                            kind=GraphEdgeKind.PRODUCED_EVIDENCE,
                            from_node_id=actor_node,
                            to_node_id=ev_node,
                            provenance=GraphProvenance(
                                source="evidence_repository.list_for_org",
                                derivation=EdgeDerivation.DIRECT,
                                explanation="Persisted governance evidence record",
                                fact_refs=[f"evidence_id:{ev.evidence_id}"],
                            ),
                        )
                    )

    return AuthorityGraph(
        organization_id=org_id,
        nodes=_stable_sort_nodes(list(nodes.values())),
        edges=_stable_sort_edges(edges),
        truncated=truncated,
        truncation_reason=truncation_reason,
    )
