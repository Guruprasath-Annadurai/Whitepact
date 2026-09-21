# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

import pytest
from pydantic import ValidationError

from responsibleai.sovereign.graph import (
    AuthorityGraph,
    EdgeDerivation,
    GraphEdge,
    GraphEdgeKind,
    GraphProvenance,
    GraphQueryBudget,
    SovereignGraphBudgetError,
    apply_graph_budget,
)


def test_edge_requires_provenance_explanation() -> None:
    with pytest.raises(ValidationError):
        GraphEdge(
            edge_id="e1",
            kind=GraphEdgeKind.OWNS,
            from_node_id="a",
            to_node_id="b",
            provenance=GraphProvenance(
                source="test",
                derivation=EdgeDerivation.DIRECT,
                explanation="   ",
            ),
        )


def test_graph_budget_enforced() -> None:
    g = AuthorityGraph(organization_id="org")
    budget = GraphQueryBudget(max_nodes=1)
    with pytest.raises(SovereignGraphBudgetError):
        apply_graph_budget(g, budget, depth=1, node_count=2, edge_count=0)
