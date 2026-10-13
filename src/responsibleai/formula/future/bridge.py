# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from responsibleai.formula.capability.closure import CapabilityClosureResult
from responsibleai.formula.capability.epistemic_compose import compose_epistemic
from responsibleai.formula.errors import CausalTenantMismatch
from responsibleai.formula.future.actors import consequence_subject_from_actor
from responsibleai.formula.future.facts import ConsequenceFact
from responsibleai.formula.future.models import ConsequenceReachability, Reversibility
from responsibleai.formula.future.persistence import compose_persistence
from responsibleai.formula.future.provenance import CausalDerivation
from responsibleai.formula.future.reversibility import compose_reversibility
from responsibleai.formula.future.rules import CausalRule, CausalRuleFamily


def _effective_reversibility(
    rule: Reversibility,
    *,
    information_sensitive: bool,
    recovery_rule: bool,
) -> Reversibility:
    if information_sensitive and not recovery_rule:
        return Reversibility.IRREVERSIBLE
    return rule


def capability_bridge_derivations(
    closure: CapabilityClosureResult,
    bridge_rules: tuple[CausalRule, ...],
) -> tuple[ConsequenceFact, ...]:
    """Seed consequences from pinned capability closure via explicit CAPABILITY_BRIDGE rules."""
    facts: list[ConsequenceFact] = []
    bridge = [r for r in bridge_rules if r.family == CausalRuleFamily.CAPABILITY_BRIDGE]
    for rule in bridge:
        if rule.tenant_id != closure.tenant_id:
            raise CausalTenantMismatch("bridge rule tenant mismatch")
        for cap in closure.facts:
            if cap.action != rule.capability_action:
                continue
            if cap.target_node_id != rule.capability_target_node_id:
                continue
            ep = compose_epistemic(cap.epistemic_status, rule.epistemic_status)
            subject = consequence_subject_from_actor(cap.actor)
            rev = _effective_reversibility(
                rule.reversibility,
                information_sensitive=rule.information_sensitive,
                recovery_rule=rule.recovery_rule,
            )
            fact = ConsequenceFact(
                tenant_id=closure.tenant_id,
                subject_id=subject,
                target_id=rule.output_target_id,
                consequence_kind=rule.output_kind,
                scope=rule.output_scope,
                reversibility=rev,
                persistence=rule.persistence,
                information_sensitive=rule.information_sensitive,
                epistemic_status=ep,
                reachability=ConsequenceReachability.SUPPORTED,
            )
            facts.append(fact)
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
        causal_depth=0,
        epistemic_status=fact.epistemic_status,
        reversibility=fact.reversibility,
        information_sensitive=fact.information_sensitive,
        subject_id=fact.subject_id,
        persistence=fact.persistence,
        capability_semantic_key=cap_semantic_key,
    )


def aggregate_consequence_fact(
    fact: ConsequenceFact,
    witness: CausalDerivation,
    *,
    recovery_rule: bool = False,
) -> ConsequenceFact:
    return ConsequenceFact(
        tenant_id=fact.tenant_id,
        subject_id=fact.subject_id,
        target_id=fact.target_id,
        consequence_kind=fact.consequence_kind,
        scope=fact.scope,
        reversibility=compose_reversibility(
            fact.reversibility, witness.reversibility, recovery_rule=recovery_rule
        ),
        information_sensitive=fact.information_sensitive or witness.information_sensitive,
        epistemic_status=compose_epistemic(fact.epistemic_status, witness.epistemic_status),
        persistence=compose_persistence(fact.persistence, witness.persistence),
        reachability=fact.reachability,
        magnitude_class=fact.magnitude_class,
    )
