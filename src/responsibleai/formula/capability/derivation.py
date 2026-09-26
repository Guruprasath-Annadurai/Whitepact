# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass

from responsibleai.formula.epistemic import EpistemicStatus


@dataclass(frozen=True, slots=True)
class CapabilityDerivation:
    rule_id: str
    output_semantic_key: tuple[str, str, tuple[str, ...], str, str]
    prerequisite_keys: tuple[tuple[str, str, tuple[str, ...], str, str], ...]
    graph_node_ids: tuple[str, ...]
    graph_edge_ids: tuple[str, ...]
    epistemic_status: EpistemicStatus
    derivation_depth: int
    route_node_ids: tuple[str, ...]
