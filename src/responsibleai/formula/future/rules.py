# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass

from responsibleai.formula.epistemic import EpistemicStatus
from responsibleai.formula.errors import CausalTenantMismatch, InvalidCausalRule
from responsibleai.formula.future.models import CausalRuleFamily, ConsequenceKind, Reversibility
from responsibleai.formula.graph.snapshot import GraphSnapshot

PrerequisitePattern = tuple[str, str]  # (consequence_kind value, target_id)


@dataclass(frozen=True, slots=True)
class CausalRule:
    rule_id: str
    tenant_id: str
    family: CausalRuleFamily
    prerequisite_patterns: tuple[PrerequisitePattern, ...]
    output_kind: ConsequenceKind
    output_subject_id: str
    output_target_id: str
    output_scope: str
    reversibility: Reversibility
    epistemic_status: EpistemicStatus
    persistence: bool = False
    information_sensitive: bool = False
    graph_edge_id: str | None = None
    capability_action: str | None = None
    capability_target_node_id: str | None = None
    recovery_rule: bool = False

    def __post_init__(self) -> None:
        if not self.rule_id.strip():
            raise InvalidCausalRule("rule_id required")
        if self.family == CausalRuleFamily.CAPABILITY_BRIDGE:
            if not self.capability_action or not self.capability_target_node_id:
                raise InvalidCausalRule("CAPABILITY_BRIDGE requires capability_action and target")
        if self.family in (
            CausalRuleFamily.PROPAGATED_EFFECT,
            CausalRuleFamily.CREDENTIAL_PROPAGATION,
            CausalRuleFamily.INFORMATION_PROPAGATION,
        ):
            if not self.graph_edge_id:
                raise InvalidCausalRule(f"{self.family} requires graph_edge_id")
        if not self.prerequisite_patterns and self.family != CausalRuleFamily.CAPABILITY_BRIDGE:
            raise InvalidCausalRule("non-bridge rules require prerequisite_patterns")


def validate_causal_rules(snapshot: GraphSnapshot, rules: tuple[CausalRule, ...]) -> None:
    seen: set[str] = set()
    for rule in rules:
        if rule.tenant_id != snapshot.tenant_id:
            raise CausalTenantMismatch(
                f"rule {rule.rule_id!r} tenant {rule.tenant_id!r} != snapshot {snapshot.tenant_id!r}"
            )
        if rule.rule_id in seen:
            raise InvalidCausalRule(f"duplicate rule_id {rule.rule_id!r}")
        seen.add(rule.rule_id)
        if rule.graph_edge_id is not None:
            edges = {e.edge_id: e for e in snapshot.edges}
            edge = edges.get(rule.graph_edge_id)
            if edge is None:
                raise InvalidCausalRule(f"unknown graph edge {rule.graph_edge_id!r}")
            if edge.tenant_id != snapshot.tenant_id:
                raise CausalTenantMismatch("graph edge tenant mismatch")
