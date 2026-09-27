# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import replace
from itertools import product

from responsibleai.formula.capability.budget import ClosureStatus
from responsibleai.formula.capability.closure import CapabilityClosureResult
from responsibleai.formula.capability.epistemic_compose import compose_epistemic
from responsibleai.formula.epistemic import EpistemicStatus
from responsibleai.formula.errors import CausalCycleError, CausalTenantMismatch
from responsibleai.formula.future.actors import consequence_subject_from_actor
from responsibleai.formula.future.blast import BlastRadius
from responsibleai.formula.future.bridge import (
    aggregate_consequence_fact,
    bridge_witness_for,
)
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
from responsibleai.formula.future.reversibility import compose_reversibility
from responsibleai.formula.future.rules import CausalRule, validate_causal_rules
from responsibleai.formula.future.serialize import (
    causal_rules_fingerprint,
    closure_fingerprint,
    compute_envelope_hash,
)
from responsibleai.formula.graph.snapshot import GraphSnapshot

_EDGE_ANCHORED_FAMILIES = frozenset(
    {
        CausalRuleFamily.PROPAGATED_EFFECT,
        CausalRuleFamily.CREDENTIAL_PROPAGATION,
        CausalRuleFamily.INFORMATION_PROPAGATION,
    }
)


def _effective_reversibility(
    rule: Reversibility,
    *,
    information_sensitive: bool,
    recovery_rule: bool,
) -> Reversibility:
    if information_sensitive and not recovery_rule:
        return Reversibility.IRREVERSIBLE
    return rule


def _active_set(
    facts: dict[ConsequenceSemanticKey, ConsequenceFact],
) -> frozenset[ConsequenceSemanticKey]:
    return frozenset(facts.keys())


def _matching_keys(
    active: frozenset[ConsequenceSemanticKey],
    kind: str,
    target: str,
) -> tuple[ConsequenceSemanticKey, ...]:
    return tuple(sorted(k for k in active if k[3] == kind and k[2] == target))


def _prereq_combinations(
    rule: CausalRule,
    active: frozenset[ConsequenceSemanticKey],
) -> tuple[tuple[ConsequenceSemanticKey, ...], ...]:
    options: list[tuple[ConsequenceSemanticKey, ...]] = []
    for kind, target in rule.prerequisite_patterns:
        matched = _matching_keys(active, kind, target)
        if not matched:
            return ()
        options.append(matched)
    return tuple(product(*options))


def _edge_allows(
    rule: CausalRule,
    snapshot: GraphSnapshot,
    prereqs: tuple[ConsequenceSemanticKey, ...],
) -> bool:
    if rule.graph_edge_id is None or rule.family not in _EDGE_ANCHORED_FAMILIES:
        return True
    edges = {e.edge_id: e for e in snapshot.edges}
    edge = edges[rule.graph_edge_id]
    return prereqs[0][2] == edge.source_id


def _resolve_output_target(
    rule: CausalRule,
    snapshot: GraphSnapshot,
    prereq_target: str,
) -> str:
    if rule.output_target_id != "*":
        return rule.output_target_id
    if not rule.graph_edge_id:
        return prereq_target
    edges = {e.edge_id: e for e in snapshot.edges}
    return edges[rule.graph_edge_id].target_id


def _witness_depth(
    dag: CausalWitnessDag,
    prereq_fps: tuple[tuple, ...],
) -> int:
    if not prereq_fps:
        return 0
    depths = []
    for fp in prereq_fps:
        w = dag.get_by_fingerprint(fp)
        if w is not None:
            depths.append(w.causal_depth)
    return max(depths, default=0) + 1


def _rebuild_aggregate(
    key: ConsequenceSemanticKey,
    facts: dict[ConsequenceSemanticKey, ConsequenceFact],
    dag: CausalWitnessDag,
) -> None:
    witnesses = dag.get_witnesses(key)
    if not witnesses:
        return
    base = facts[key]
    ep = compose_epistemic(*(w.epistemic_status for w in witnesses))
    rev = witnesses[0].reversibility
    for w in witnesses[1:]:
        rev = compose_reversibility(rev, w.reversibility)
    info = any(w.information_sensitive for w in witnesses)
    facts[key] = ConsequenceFact(
        tenant_id=base.tenant_id,
        subject_id=base.subject_id,
        target_id=base.target_id,
        consequence_kind=base.consequence_kind,
        scope=base.scope,
        reversibility=rev,
        persistence=base.persistence,
        information_sensitive=info,
        epistemic_status=ep,
        reachability=base.reachability,
        magnitude_class=base.magnitude_class,
    )


def _build_derived_fact(
    rule: CausalRule,
    snapshot: GraphSnapshot,
    prereqs: tuple[ConsequenceSemanticKey, ...],
    facts: dict[ConsequenceSemanticKey, ConsequenceFact],
    witness: CausalDerivation,
) -> ConsequenceFact:
    prereq_target = prereqs[0][2]
    out_target = _resolve_output_target(rule, snapshot, prereq_target)
    ep = compose_epistemic(
        *[facts[p].epistemic_status for p in prereqs],
        witness.epistemic_status,
    )
    info = rule.information_sensitive or any(facts[p].information_sensitive for p in prereqs)
    rev = rule.reversibility
    for p in prereqs:
        rev = compose_reversibility(
            facts[p].reversibility, rev, recovery_rule=rule.recovery_rule
        )
    if info and not rule.recovery_rule:
        rev = Reversibility.IRREVERSIBLE
    return ConsequenceFact(
        tenant_id=snapshot.tenant_id,
        subject_id=witness.subject_id,
        target_id=out_target,
        consequence_kind=rule.output_kind,
        scope=rule.output_scope,
        reversibility=rev,
        persistence=rule.persistence,
        information_sensitive=info,
        epistemic_status=ep,
        reachability=ConsequenceReachability.SUPPORTED,
    )


def _iter_rule_applications(
    effect_rules: tuple[CausalRule, ...],
    active: frozenset[ConsequenceSemanticKey],
    snapshot: GraphSnapshot,
    facts: dict[ConsequenceSemanticKey, ConsequenceFact],
    dag: CausalWitnessDag,
) -> list[tuple[CausalRule, tuple[ConsequenceSemanticKey, ...], tuple[tuple, ...]]]:
    """Deterministic rule / prereq / witness-fingerprint combinations."""
    apps: list[tuple[CausalRule, tuple[ConsequenceSemanticKey, ...], tuple[tuple, ...]]] = []
    for rule in sorted(effect_rules, key=lambda r: r.rule_id):
        for prereqs in _prereq_combinations(rule, active):
            if not _edge_allows(rule, snapshot, prereqs):
                continue
            witness_lists = [dag.get_witnesses(p) for p in prereqs]
            if any(not wl for wl in witness_lists):
                continue
            for combo in product(*witness_lists):
                fps = tuple(w.witness_fingerprint() for w in combo)
                apps.append((rule, prereqs, fps))
    return apps


def _novel_application_exists(
    apps: list[tuple[CausalRule, tuple[ConsequenceSemanticKey, ...], tuple[tuple, ...]]],
    snapshot: GraphSnapshot,
    facts: dict[ConsequenceSemanticKey, ConsequenceFact],
    dag: CausalWitnessDag,
    b: FutureEnvelopeBudget,
) -> bool:
    for rule, prereqs, prereq_fps in apps:
        causal_depth = _witness_depth(dag, prereq_fps)
        if causal_depth > b.max_path_depth:
            return True
        ep = compose_epistemic(
            *[facts[p].epistemic_status for p in prereqs], rule.epistemic_status
        )
        prereq_target = prereqs[0][2]
        out_target = _resolve_output_target(rule, snapshot, prereq_target)
        info = rule.information_sensitive or any(facts[p].information_sensitive for p in prereqs)
        rev = rule.reversibility
        for p in prereqs:
            rev = compose_reversibility(
                facts[p].reversibility, rev, recovery_rule=rule.recovery_rule
            )
        if info and not rule.recovery_rule:
            rev = Reversibility.IRREVERSIBLE
        key = (
            snapshot.tenant_id,
            rule.output_subject_id,
            out_target,
            rule.output_kind.value,
            rule.output_scope,
        )
        witness = CausalDerivation(
            rule_id=rule.rule_id,
            output_key=key,
            prerequisite_keys=prereqs,
            prerequisite_witness_fingerprints=prereq_fps,
            graph_edge_ids=(rule.graph_edge_id,) if rule.graph_edge_id else (),
            trajectory_depth=0,
            causal_depth=causal_depth,
            epistemic_status=ep,
            reversibility=rev,
            information_sensitive=info,
            subject_id=rule.output_subject_id,
        )
        if dag.has_fingerprint(witness.witness_fingerprint()):
            continue
        return True
    return False


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

    upstream_incomplete = closure.status == ClosureStatus.INCOMPLETE

    validate_causal_rules(snapshot, causal_rules)
    bridge_rules = tuple(r for r in causal_rules if r.family == CausalRuleFamily.CAPABILITY_BRIDGE)
    effect_rules = tuple(r for r in causal_rules if r.family != CausalRuleFamily.CAPABILITY_BRIDGE)

    facts: dict[ConsequenceSemanticKey, ConsequenceFact] = {}
    dag = CausalWitnessDag()
    blocked: list[str] = []
    if upstream_incomplete:
        blocked.append("capability_closure_incomplete")
        for note in closure.unresolved_notes:
            blocked.append(f"closure:{note}")
    usage = {
        "states": 0,
        "consequences": 0,
        "derivations": 0,
        "rule_applications": 0,
        "trajectories": 0,
        "frontier": 0,
    }
    truncated = False

    def try_add_witness(
        witness: CausalDerivation,
        fact: ConsequenceFact,
        rule: CausalRule,
    ) -> bool:
        nonlocal truncated
        fp = witness.witness_fingerprint()
        if dag.has_fingerprint(fp):
            return False
        if witness.causal_depth > b.max_path_depth:
            truncated = True
            blocked.append("max_path_depth")
            return False
        if len(dag.all_witnesses()) >= b.max_derivations:
            truncated = True
            blocked.append("max_derivations")
            return False
        if usage["trajectories"] >= b.max_trajectories:
            truncated = True
            blocked.append("max_trajectories")
            return False
        key = fact.semantic_key()
        novel_fact = key not in facts
        if novel_fact and len(facts) >= b.max_consequences:
            truncated = True
            blocked.append("max_consequences")
            return False
        try:
            if not dag.add_witness(witness):
                return False
        except CausalCycleError:
            return False
        usage["derivations"] = len(dag.all_witnesses())
        usage["trajectories"] += 1
        if novel_fact:
            facts[key] = fact
            usage["consequences"] = len(facts)
        else:
            facts[key] = aggregate_consequence_fact(
                facts[key], witness, recovery_rule=rule.recovery_rule
            )
        return True

    for cap in sorted(closure.facts, key=lambda c: c.semantic_key()):
        for rule in sorted(bridge_rules, key=lambda r: r.rule_id):
            if (
                cap.action != rule.capability_action
                or cap.target_node_id != rule.capability_target_node_id
            ):
                continue
            ep = compose_epistemic(cap.epistemic_status, rule.epistemic_status)
            subject = consequence_subject_from_actor(cap.actor)
            info = rule.information_sensitive
            rev = _effective_reversibility(
                rule.reversibility,
                information_sensitive=info,
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
                information_sensitive=info,
                epistemic_status=ep,
                reachability=ConsequenceReachability.SUPPORTED,
            )
            w = bridge_witness_for(rule, cap.semantic_key(), fact, 0)
            try_add_witness(w, fact, rule)

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
        apps = _iter_rule_applications(effect_rules, active, snapshot, facts, dag)
        for rule, prereqs, prereq_fps in apps:
            causal_depth = _witness_depth(dag, prereq_fps)
            ep = compose_epistemic(
                *[facts[p].epistemic_status for p in prereqs], rule.epistemic_status
            )
            info = rule.information_sensitive or any(
                facts[p].information_sensitive for p in prereqs
            )
            rev = rule.reversibility
            for p in prereqs:
                rev = compose_reversibility(
                    facts[p].reversibility, rev, recovery_rule=rule.recovery_rule
                )
            if info and not rule.recovery_rule:
                rev = Reversibility.IRREVERSIBLE
            prereq_target = prereqs[0][2]
            out_target = _resolve_output_target(rule, snapshot, prereq_target)
            key = (
                snapshot.tenant_id,
                rule.output_subject_id,
                out_target,
                rule.output_kind.value,
                rule.output_scope,
            )
            witness = CausalDerivation(
                rule_id=rule.rule_id,
                output_key=key,
                prerequisite_keys=prereqs,
                prerequisite_witness_fingerprints=prereq_fps,
                graph_edge_ids=(rule.graph_edge_id,) if rule.graph_edge_id else (),
                trajectory_depth=step,
                causal_depth=causal_depth,
                epistemic_status=ep,
                reversibility=rev,
                information_sensitive=info,
                subject_id=rule.output_subject_id,
            )
            if dag.has_fingerprint(witness.witness_fingerprint()):
                continue
            if usage["rule_applications"] >= b.max_rule_applications:
                truncated = True
                blocked.append("max_rule_applications")
                break
            usage["rule_applications"] += 1
            fact = _build_derived_fact(rule, snapshot, prereqs, facts, witness)
            if try_add_witness(witness, fact, rule):
                step_added = True
        if len(reachable_states) >= b.max_states:
            truncated = True
            blocked.append("max_states")
            break
        reachable_states.append(ReachableWorldState(step=step, active_keys=_active_set(facts)))
        usage["states"] = len(reachable_states)
        if not step_added:
            break

    final_active = _active_set(facts)
    final_apps = _iter_rule_applications(effect_rules, final_active, snapshot, facts, dag)
    if not truncated and _novel_application_exists(final_apps, snapshot, facts, dag, b):
        truncated = True
        blocked.append("horizon_exhausted")

    status = (
        EnvelopeStatus.INCOMPLETE
        if truncated or upstream_incomplete
        else EnvelopeStatus.COMPLETE
    )
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
        capability_closure_status=closure.status.value,
        capability_unresolved_notes=closure.unresolved_notes,
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
