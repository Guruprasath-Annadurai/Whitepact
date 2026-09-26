# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass

from responsibleai.formula.epistemic import EpistemicStatus

SemanticKey = tuple[str, str, tuple[str, ...], str, str]


@dataclass(frozen=True, slots=True)
class CapabilityDerivation:
    rule_id: str
    output_semantic_key: SemanticKey
    prerequisite_keys: tuple[SemanticKey, ...]
    graph_node_ids: tuple[str, ...]
    graph_edge_ids: tuple[str, ...]
    epistemic_status: EpistemicStatus
    derivation_depth: int
    route_node_ids: tuple[str, ...]

    def witness_fingerprint(self) -> tuple:
        return (
            self.rule_id,
            self.output_semantic_key,
            self.prerequisite_keys,
            self.graph_edge_ids,
            self.route_node_ids,
            self.derivation_depth,
        )
