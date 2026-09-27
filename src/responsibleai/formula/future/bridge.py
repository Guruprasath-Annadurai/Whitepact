# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from responsibleai.formula.capability.closure import CapabilityClosureResult
from responsibleai.formula.capability.epistemic_compose import compose_epistemic
from responsibleai.formula.errors import CausalTenantMismatch
from responsibleai.formula.future.facts import ConsequenceFact
from responsibleai.formula.future.models import ConsequenceReachability
from responsibleai.formula.future.provenance import CausalDerivation
from responsibleai.formula.future.rules import CausalRule, CausalRuleFamily


def capability_bridge_derivations(
    closure: CapabilityClosureResult,
    bridge_rules: tuple[CausalRule, ...],
) -> tuple[ConsequenceFact, ...]:
    """Seed consequences from pinned capability closure via explicit CAPABILITY_BRIDGE rules."""
    facts: list[ConsequenceFact] = []
    bridge = [r for r in bridge_rules if r.family == CausalRuleFamily.CAPABILITY_BRIDGE]
    cap_by_key = {f.semantic_key(): f for f in closure.facts}
    for rule in bridge:
        if rule.tenant_id != closure.tenant_id:
            raise CausalTenantMismatch("bridge rule tenant mismatch")
        for cap in closure.facts:
            if cap.action != rule.capability_action:
                continue
            if cap.target_node_id != rule.capability_target_node_id:
                continue
            ep = compose_epistemic(cap.epistemic_status, rule.epistemic_status)
            subject = cap.actor.member_ids[0] if cap.actor.member_ids else "unknown"
            fact = ConsequenceFact(
                tenant_id=closure.tenant_id,
                subject_id=subject,
                target_id=rule.output_target_id,
                consequence_kind=rule.output_kind,
                scope=rule.output_scope,
                reversibility=rule.reversibility,
                persistence=rule.persistence,
                information_sensitive=rule.information_sensitive,
                epistemic_status=ep,
                reachability=ConsequenceReachability.SUPPORTED,
            )
            facts.append(fact)
            _ = cap_by_key  # pinned closure reference — immutability is caller responsibility
    return tuple(facts)


def bridge_witness_for(
    rule: CausalRule,
    cap_semantic_key: tuple,
    fact: ConsequenceFact,
    depth: int,
) -> CausalDerivation:
    return CausalDerivation(
        rule_id=rule.rule_id,
        output_key=fact.semantic_key(),
        prerequisite_keys=(),
        prerequisite_witness_fingerprints=(),
        graph_edge_ids=(),
        trajectory_depth=depth,
        epistemic_status=fact.epistemic_status,
        capability_semantic_key=cap_semantic_key,
    )
