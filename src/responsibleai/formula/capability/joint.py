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
from responsibleai.formula.errors import CapabilityTenantMismatch, InvalidCapability
from responsibleai.formula.graph.kinds import NodeKind
from responsibleai.formula.graph.snapshot import GraphSnapshot

_JOINT_ACTOR_KINDS = frozenset(
    {
        NodeKind.AGENT,
        NodeKind.HUMAN,
        NodeKind.TOOL,
        NodeKind.MCP_SERVER,
        NodeKind.API,
        NodeKind.SERVICE,
    }
)


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
        canonical_members = tuple(sorted(set(self.coalition_member_ids)))
        if canonical_members != self.coalition_member_ids:
            object.__setattr__(self, "coalition_member_ids", canonical_members)
        canonical_keys = tuple(sorted(self.required_semantic_keys))
        if canonical_keys != self.required_semantic_keys:
            object.__setattr__(self, "required_semantic_keys", canonical_keys)


def validate_joint_rules(
    snapshot: GraphSnapshot,
    joint_rules: tuple[JointCapabilityRule, ...],
) -> None:
    nodes = {n.node_id: n for n in snapshot.nodes}
    seen: dict[str, JointCapabilityRule] = {}
    for rule in joint_rules:
        if rule.tenant_id != snapshot.tenant_id:
            raise CapabilityTenantMismatch("joint rule tenant mismatch")
        if not rule.required_semantic_keys:
            raise InvalidCapability("joint rule requires non-empty prerequisites")
        if not rule.coalition_member_ids:
            raise InvalidCapability("joint rule requires non-empty coalition")
        if rule.target_node_id not in nodes:
            raise InvalidCapability(f"joint target {rule.target_node_id} not in snapshot")
        tgt = nodes[rule.target_node_id]
        if tgt.tenant_id != snapshot.tenant_id:
            raise CapabilityTenantMismatch("joint target tenant mismatch")
        for member in rule.coalition_member_ids:
            if member not in nodes:
                raise InvalidCapability(f"joint coalition member {member} not in snapshot")
            node = nodes[member]
            if node.tenant_id != snapshot.tenant_id:
                raise CapabilityTenantMismatch("joint coalition member tenant mismatch")
            if node.kind not in _JOINT_ACTOR_KINDS:
                raise InvalidCapability(f"invalid coalition member kind {node.kind}")
        for req in rule.required_semantic_keys:
            if req[0] != snapshot.tenant_id:
                raise CapabilityTenantMismatch("joint prerequisite tenant mismatch")
        if rule.rule_id in seen:
            if seen[rule.rule_id] != rule:
                raise InvalidCapability(f"conflicting joint rule id {rule.rule_id}")
        else:
            seen[rule.rule_id] = rule


def apply_joint_rules(
    snapshot: GraphSnapshot,
    state: CapabilityClosureState,
    joint_rules: tuple[JointCapabilityRule, ...],
    *,
    max_path_depth: int,
    rule_budget: int,
    max_facts: int,
    max_derivations: int,
) -> int:
    """Return count of successful witness productions."""
    if not joint_rules:
        return 0
    produced = 0
    for rule in sorted(joint_rules, key=lambda r: (r.rule_id, r.target_node_id, r.action)):
        if produced >= rule_budget:
            state.budget_truncated = True
            break
        missing = [k for k in rule.required_semantic_keys if k not in state.facts_by_key]
        if missing:
            continue
        prereq_fps: list[tuple] = []
        epistemic = rule.epistemic_status
        max_prereq_depth = 0
        for k in rule.required_semantic_keys:
            witnesses = state.sorted_witnesses(k)
            if not witnesses:
                continue
            shallow = witnesses[0]
            prereq_fps.append(shallow.witness_fingerprint())
            max_prereq_depth = max(max_prereq_depth, shallow.derivation_depth)
            for w in witnesses:
                epistemic = compose_epistemic(epistemic, w.epistemic_status)
        route = tuple(rule.coalition_member_ids) + (rule.target_node_id,)
        depth = max(route_derivation_depth(route), max_prereq_depth + 1)
        if depth > max_path_depth:
            state.frontier_blocked = True
            state.truncation_notes.append(f"max_path_depth exhausted for joint rule {rule.rule_id}")
            continue
        actor = CapabilityActor.coalition(rule.tenant_id, rule.coalition_member_ids)
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
            prerequisite_witness_fingerprints=tuple(prereq_fps),
            graph_node_ids=route,
            graph_edge_ids=(),
            epistemic_status=epistemic,
            derivation_depth=depth,
            route_node_ids=route,
            support_kind=CapabilityKind.COMPOSED,
            support_is_direct=False,
        )
        witness_added, _ = state.add_witness(
            fact,
            witness,
            max_facts=max_facts,
            max_derivations=max_derivations,
        )
        if witness_added:
            produced += 1
    return produced
