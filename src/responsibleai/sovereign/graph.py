# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Authority topology graph with mandatory edge provenance."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from responsibleai.sovereign.errors import SovereignGraphBudgetError


class GraphNodeKind(StrEnum):
    HUMAN = "human"
    AGENT = "agent"
    SERVICE_ACCOUNT = "service_account"
    APPLICATION = "application"
    MCP_SERVER = "mcp_server"
    TOOL = "tool"
    POLICY = "policy"
    CAPABILITY = "capability"
    DELEGATION = "delegation"
    APPROVAL = "approval"
    EXECUTION_GRANT = "execution_grant"
    EFFECT = "effect"
    EVIDENCE = "evidence"
    ORGANIZATION = "organization"


class GraphEdgeKind(StrEnum):
    OWNS = "OWNS"
    MEMBER_OF = "MEMBER_OF"
    DELEGATED_TO = "DELEGATED_TO"
    CAN_CALL = "CAN_CALL"
    CAN_REACH = "CAN_REACH"
    GOVERNED_BY = "GOVERNED_BY"
    REQUIRES_APPROVAL = "REQUIRES_APPROVAL"
    AUTHORIZED_BY = "AUTHORIZED_BY"
    ISSUED = "ISSUED"
    EXECUTED = "EXECUTED"
    PRODUCED_EVIDENCE = "PRODUCED_EVIDENCE"
    REVOKED_BY = "REVOKED_BY"
    DEPENDS_ON = "DEPENDS_ON"


class EdgeDerivation(StrEnum):
    DIRECT = "DIRECT"
    DELEGATED = "DELEGATED"
    TRANSITIVE = "TRANSITIVE"
    DERIVED = "DERIVED"
    UNKNOWN = "UNKNOWN"


class GraphProvenance(BaseModel):
    source: str
    derivation: EdgeDerivation
    explanation: str
    fact_refs: list[str] = Field(default_factory=list)


class GraphNode(BaseModel):
    node_id: str
    kind: GraphNodeKind
    label: str
    organization_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    edge_id: str
    kind: GraphEdgeKind
    from_node_id: str
    to_node_id: str
    provenance: GraphProvenance

    @model_validator(mode="after")
    def _provenance_required(self) -> GraphEdge:
        if not self.provenance.explanation.strip():
            raise ValueError("Graph edge provenance explanation is required")
        return self


class AuthorityGraph(BaseModel):
    organization_id: str
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    truncated: bool = False
    truncation_reason: str | None = None

    def node_index(self) -> dict[str, GraphNode]:
        return {n.node_id: n for n in self.nodes}


class GraphQueryBudget(BaseModel):
    max_depth: int = 8
    max_nodes: int = 500
    max_edges: int = 2000


def apply_graph_budget(
    graph: AuthorityGraph,
    budget: GraphQueryBudget,
    *,
    depth: int,
    node_count: int,
    edge_count: int,
) -> AuthorityGraph:
    if (
        depth > budget.max_depth
        or node_count > budget.max_nodes
        or edge_count > budget.max_edges
    ):
        raise SovereignGraphBudgetError(
            "Authority graph query exceeded budget "
            f"(depth={depth}, nodes={node_count}, edges={edge_count})"
        )
    return graph
