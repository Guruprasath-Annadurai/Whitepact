# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass

from responsibleai.formula.capability.actors import CapabilityActor
from responsibleai.formula.capability.derivation import CapabilityDerivation, SemanticKey
from responsibleai.formula.capability.epistemic_compose import compose_epistemic
from responsibleai.formula.capability.facts import CapabilityFact
from responsibleai.formula.capability.models import CapabilityKind
from responsibleai.formula.capability.routes import route_derivation_depth
from responsibleai.formula.capability.rules import RuleId
from responsibleai.formula.capability.state import CapabilityClosureState
from responsibleai.formula.epistemic import EpistemicStatus
from responsibleai.formula.errors import CapabilityTenantMismatch


@dataclass(frozen=True, slots=True)
class JointCapabilityRule:
    rule_id: str
    tenant_id: str
    required_semantic_keys: tuple[SemanticKey, ...]
    coalition_member_ids: tuple[str, ...]
    action: str
    target_node_id: str
    epistemic_status: EpistemicStatus = EpistemicStatus.DECLARED

    def __post_init__(self) -> None:
        canonical = tuple(sorted(set(self.coalition_member_ids)))
        if canonical != self.coalition_member_ids:
            object.__setattr__(self, "coalition_member_ids", canonical)


def apply_joint_rules(
    state: CapabilityClosureState,
    joint_rules: tuple[JointCapabilityRule, ...],
    *,
    max_path_depth: int,
    rule_budget: int,
) -> int:
    """Return count of successful witness productions."""
    if not joint_rules:
        return 0
    tenant_id = next(iter(state.facts_by_key.values())).tenant_id if state.facts_by_key else None
    produced = 0
    for rule in sorted(joint_rules, key=lambda r: r.rule_id):
        if produced >= rule_budget:
            state.budget_truncated = True
            break
        if tenant_id is not None and rule.tenant_id != tenant_id:
            raise CapabilityTenantMismatch("joint rule tenant mismatch")
        missing = [k for k in rule.required_semantic_keys if k not in state.facts_by_key]
        if missing:
            continue
        route = tuple(rule.coalition_member_ids) + (rule.target_node_id,)
        depth = route_derivation_depth(route)
        prereq_depths = [state.max_depth(k) for k in rule.required_semantic_keys]
        depth = max(depth, max(prereq_depths, default=0) + 1)
        if depth > max_path_depth:
            state.frontier_blocked = True
            state.truncation_notes.append(f"max_path_depth exhausted for joint rule {rule.rule_id}")
            continue
        actor = CapabilityActor.coalition(rule.tenant_id, rule.coalition_member_ids)
        epistemic = rule.epistemic_status
        for k in rule.required_semantic_keys:
            epistemic = compose_epistemic(epistemic, state.facts_by_key[k].epistemic_status)
        fact = CapabilityFact(
            tenant_id=rule.tenant_id,
            actor=actor,
            action=rule.action,
            target_node_id=rule.target_node_id,
            kind=CapabilityKind.COMPOSED,
            epistemic_status=epistemic,
            is_direct=False,
        )
        witness = CapabilityDerivation(
            rule_id=RuleId.JOINT_COALITION,
            output_semantic_key=fact.semantic_key(),
            prerequisite_keys=rule.required_semantic_keys,
            graph_node_ids=route,
            graph_edge_ids=(),
            epistemic_status=epistemic,
            derivation_depth=depth,
            route_node_ids=route,
        )
        witness_added, _ = state.add_witness(fact, witness, is_direct=False)
        if witness_added:
            produced += 1
    return produced
