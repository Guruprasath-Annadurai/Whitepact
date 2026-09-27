# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import replace

from responsibleai.formula.capability.closure import CapabilityClosureResult
from responsibleai.formula.capability.epistemic_compose import compose_epistemic
from responsibleai.formula.epistemic import EpistemicStatus
from responsibleai.formula.errors import CausalTenantMismatch
from responsibleai.formula.future.blast import BlastRadius
from responsibleai.formula.future.bridge import bridge_witness_for
from responsibleai.formula.future.budget import FutureEnvelopeBudget
from responsibleai.formula.future.envelope import ReachableWorldState, SafeFutureEnvelope
from responsibleai.formula.future.facts import ConsequenceFact, ConsequenceSemanticKey
from responsibleai.formula.future.models import (
    CausalRuleFamily,
    ConsequenceReachability,
    EnvelopeStatus,
    Reversibility,
)
from responsibleai.formula.future.provenance import CausalDerivation, CausalWitnessDag
from responsibleai.formula.future.rules import CausalRule, validate_causal_rules
from responsibleai.formula.future.serialize import (
    causal_rules_fingerprint,
    closure_fingerprint,
    compute_envelope_hash,
)
from responsibleai.formula.graph.snapshot import GraphSnapshot

_REV_ORDER = (
    Reversibility.UNKNOWN,
    Reversibility.CONDITIONALLY_REVERSIBLE,
    Reversibility.REVERSIBLE,
    Reversibility.IRREVERSIBLE,
)


def _active_set(
    facts: dict[ConsequenceSemanticKey, ConsequenceFact],
) -> frozenset[ConsequenceSemanticKey]:
    return frozenset(facts.keys())


def _resolve_output_target(rule: CausalRule, snapshot: GraphSnapshot, prereq_target: str) -> str:
    if rule.output_target_id != "*":
        return rule.output_target_id
    if not rule.graph_edge_id:
        return prereq_target
    edges = {e.edge_id: e for e in snapshot.edges}
    return edges[rule.graph_edge_id].target_id


def _any_applicable_rules(
    rules: tuple[CausalRule, ...],
    active: frozenset[ConsequenceSemanticKey],
) -> bool:
    return any(_prereqs_satisfied(rule, active) is not None for rule in rules)


def _prereqs_satisfied(
    rule: CausalRule,
    active: frozenset[ConsequenceSemanticKey],
) -> tuple[ConsequenceSemanticKey, ...] | None:
    matched: list[ConsequenceSemanticKey] = []
    for kind, target in rule.prerequisite_patterns:
        found = next((key for key in active if key[3] == kind and key[2] == target), None)
        if found is None:
            return None
        matched.append(found)
    return tuple(matched)


def _merge_reversibility(
    existing: Reversibility, new: Reversibility, recovery: bool
) -> Reversibility:
    if recovery and existing == Reversibility.IRREVERSIBLE and new == Reversibility.REVERSIBLE:
        return Reversibility.CONDITIONALLY_REVERSIBLE
    return _REV_ORDER[max(_REV_ORDER.index(existing), _REV_ORDER.index(new))]


def _effective_reversibility(
    rule: Reversibility,
    *,
    information_sensitive: bool,
    recovery_rule: bool,
) -> Reversibility:
    if information_sensitive and not recovery_rule:
        return Reversibility.IRREVERSIBLE
    return rule


def compute_safe_future_envelope(
    snapshot: GraphSnapshot,
    closure: CapabilityClosureResult,
    *,
    causal_rules: tuple[CausalRule, ...] = (),
    budget: FutureEnvelopeBudget | None = None,
    horizon: int | None = None,
) -> SafeFutureEnvelope:
    """Bounded causal consequence reachability — does not authorize execution."""
    b = budget or FutureEnvelopeBudget()
    b.validate()
    h = horizon if horizon is not None else b.max_horizon_steps
    if h <= 0 or h > b.max_horizon_steps:
        raise ValueError("horizon must be positive and <= budget.max_horizon_steps")

    if closure.tenant_id != snapshot.tenant_id:
        raise CausalTenantMismatch("closure tenant != snapshot tenant")
    if closure.graph_content_hash != snapshot.content_hash:
        raise CausalTenantMismatch("closure graph hash != snapshot content hash")

    validate_causal_rules(snapshot, causal_rules)
    bridge_rules = tuple(r for r in causal_rules if r.family == CausalRuleFamily.CAPABILITY_BRIDGE)
    effect_rules = tuple(r for r in causal_rules if r.family != CausalRuleFamily.CAPABILITY_BRIDGE)

    facts: dict[ConsequenceSemanticKey, ConsequenceFact] = {}
    dag = CausalWitnessDag()
    blocked: list[str] = []
    usage = {
        "states": 0,
        "consequences": 0,
        "derivations": 0,
        "rule_applications": 0,
        "trajectories": 0,
        "frontier": 0,
    }
    truncated = False

    def add_fact(fact: ConsequenceFact, witness: CausalDerivation, rule: CausalRule) -> bool:
        nonlocal truncated
        if len(facts) >= b.max_consequences:
            truncated = True
            blocked.append("max_consequences")
            return False
        if len(dag.all_witnesses()) >= b.max_derivations:
            truncated = True
            blocked.append("max_derivations")
            return False
        key = fact.semantic_key()
        if key in facts:
            existing = facts[key]
            facts[key] = ConsequenceFact(
                tenant_id=existing.tenant_id,
                subject_id=existing.subject_id,
                target_id=existing.target_id,
                consequence_kind=existing.consequence_kind,
                scope=existing.scope,
                reversibility=_merge_reversibility(
                    existing.reversibility, fact.reversibility, rule.recovery_rule
                ),
                persistence=existing.persistence,
                information_sensitive=existing.information_sensitive or fact.information_sensitive,
                epistemic_status=compose_epistemic(
                    existing.epistemic_status, fact.epistemic_status
                ),
                reachability=existing.reachability,
                magnitude_class=existing.magnitude_class,
            )
            return False
        dag.add_witness(witness)
        facts[key] = fact
        usage["consequences"] = len(facts)
        usage["derivations"] = len(dag.all_witnesses())
        return True

    for cap in closure.facts:
        for rule in bridge_rules:
            if (
                cap.action != rule.capability_action
                or cap.target_node_id != rule.capability_target_node_id
            ):
                continue
            ep = compose_epistemic(cap.epistemic_status, rule.epistemic_status)
            subject = cap.actor.member_ids[0] if cap.actor.member_ids else "unknown"
            fact = ConsequenceFact(
                tenant_id=closure.tenant_id,
                subject_id=subject,
                target_id=rule.output_target_id,
                consequence_kind=rule.output_kind,
                scope=rule.output_scope,
                reversibility=_effective_reversibility(
                    rule.reversibility,
                    information_sensitive=rule.information_sensitive,
                    recovery_rule=rule.recovery_rule,
                ),
                persistence=rule.persistence,
                information_sensitive=rule.information_sensitive,
                epistemic_status=ep,
                reachability=ConsequenceReachability.SUPPORTED,
            )
            w = bridge_witness_for(rule, cap.semantic_key(), fact, 0)
            add_fact(fact, w, rule)

    reachable_states: list[ReachableWorldState] = [
        ReachableWorldState(step=0, active_keys=_active_set(facts))
    ]
    usage["states"] = 1

    for step in range(1, h + 1):
        if truncated:
            break
        usage["frontier"] += 1
        if usage["frontier"] > b.max_frontier:
            truncated = True
            blocked.append("max_frontier")
            break
        active = _active_set(facts)
        step_added = False
        for rule in effect_rules:
            if usage["rule_applications"] >= b.max_rule_applications:
                truncated = True
                blocked.append("max_rule_applications")
                break
            prereqs = _prereqs_satisfied(rule, active)
            if prereqs is None:
                continue
            usage["rule_applications"] += 1
            prereq_target = prereqs[0][2]
            out_target = _resolve_output_target(rule, snapshot, prereq_target)
            ep = compose_epistemic(
                *[facts[p].epistemic_status for p in prereqs], rule.epistemic_status
            )
            rev = rule.reversibility
            for p in prereqs:
                rev = _merge_reversibility(facts[p].reversibility, rev, rule.recovery_rule)
            if any(facts[p].information_sensitive for p in prereqs) and not rule.recovery_rule:
                rev = Reversibility.IRREVERSIBLE
            fact = ConsequenceFact(
                tenant_id=snapshot.tenant_id,
                subject_id=rule.output_subject_id,
                target_id=out_target,
                consequence_kind=rule.output_kind,
                scope=rule.output_scope,
                reversibility=rev,
                persistence=rule.persistence,
                information_sensitive=rule.information_sensitive,
                epistemic_status=ep,
                reachability=ConsequenceReachability.SUPPORTED,
            )
            fingerprints = tuple(
                w.witness_fingerprint()
                for p in prereqs
                for w in [dag.get_witness(p)]
                if w is not None
            )
            witness = CausalDerivation(
                rule_id=rule.rule_id,
                output_key=fact.semantic_key(),
                prerequisite_keys=prereqs,
                prerequisite_witness_fingerprints=fingerprints,
                graph_edge_ids=(rule.graph_edge_id,) if rule.graph_edge_id else (),
                trajectory_depth=step,
                epistemic_status=ep,
            )
            if add_fact(fact, witness, rule):
                step_added = True
                usage["trajectories"] += 1
        reachable_states.append(ReachableWorldState(step=step, active_keys=_active_set(facts)))
        usage["states"] = len(reachable_states)
        if usage["states"] >= b.max_states:
            truncated = True
            blocked.append("max_states")
            break
        if not step_added:
            break

    final_active = _active_set(facts)
    if not truncated and _any_applicable_rules(effect_rules, final_active):
        truncated = True
        blocked.append("horizon_exhausted")

    status = EnvelopeStatus.INCOMPLETE if truncated else EnvelopeStatus.COMPLETE
    ordered_facts = tuple(sorted(facts.values(), key=lambda f: f.semantic_key()))
    ep_summary = (
        compose_epistemic(*(f.epistemic_status for f in ordered_facts))
        if ordered_facts
        else EpistemicStatus.UNKNOWN
    )
    blast = BlastRadius(
        tenant_id=snapshot.tenant_id,
        affected_actors=frozenset(f.subject_id for f in ordered_facts),
        affected_resources=frozenset(
            f.target_id for f in ordered_facts if "CHANGE" in f.consequence_kind.value
        ),
        affected_systems=frozenset(),
        affected_data_objects=frozenset(f.target_id for f in ordered_facts),
        external_targets=frozenset(
            f.target_id for f in ordered_facts if "EXTERNAL" in f.consequence_kind.value
        ),
        propagation_depth=max((s.step for s in reachable_states), default=0),
    )

    base = SafeFutureEnvelope(
        tenant_id=snapshot.tenant_id,
        snapshot_id=f"{snapshot.version.version_number}:{snapshot.content_hash}",
        graph_content_hash=snapshot.content_hash,
        capability_closure_fingerprint=closure_fingerprint(closure),
        causal_rules_fingerprint=causal_rules_fingerprint(causal_rules),
        horizon=h,
        status=status,
        consequence_facts=ordered_facts,
        causal_derivations=dag.all_witnesses(),
        reachable_states=tuple(reachable_states),
        blast_radius=blast,
        blocked_frontier=tuple(dict.fromkeys(blocked)),
        budget=b,
        budget_usage=usage,
        epistemic_summary=ep_summary,
        canonical_hash="",
    )
    return replace(base, canonical_hash=compute_envelope_hash(base))
