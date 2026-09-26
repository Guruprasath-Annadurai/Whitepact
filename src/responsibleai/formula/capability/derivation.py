# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass

from responsibleai.formula.capability.models import CapabilityKind
from responsibleai.formula.epistemic import EpistemicStatus

SemanticKey = tuple[str, str, tuple[str, ...], str, str]


@dataclass(frozen=True, slots=True)
class CapabilityDerivation:
    rule_id: str
    output_semantic_key: SemanticKey
    prerequisite_keys: tuple[SemanticKey, ...]
    prerequisite_witness_fingerprints: tuple[tuple, ...]
    graph_node_ids: tuple[str, ...]
    graph_edge_ids: tuple[str, ...]
    epistemic_status: EpistemicStatus
    derivation_depth: int
    route_node_ids: tuple[str, ...]
    support_kind: CapabilityKind
    support_is_direct: bool

    def witness_fingerprint(self) -> tuple:
        """Distinct supports: structural route + rule + prereq witness refs + epistemic."""
        return (
            self.rule_id,
            self.output_semantic_key,
            self.prerequisite_keys,
            self.prerequisite_witness_fingerprints,
            self.graph_edge_ids,
            self.route_node_ids,
            self.derivation_depth,
            self.epistemic_status.value,
            self.support_kind.value,
            self.support_is_direct,
        )


def witness_sort_key(witness: CapabilityDerivation) -> tuple:
    return (
        witness.derivation_depth,
        witness.route_node_ids,
        witness.witness_fingerprint(),
    )
