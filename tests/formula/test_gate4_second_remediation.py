# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""Gate 4 second semantic remediation (G4-P1-A/B/C, G4-P2)."""

from __future__ import annotations

from tests.formula.helpers_gate3 import build_snapshot, edge, node

from responsibleai.formula.capability import compute_capability_closure
from responsibleai.formula.epistemic import EpistemicStatus
from responsibleai.formula.future.actors import consequence_subject_from_members
from responsibleai.formula.future.budget import FutureEnvelopeBudget
from responsibleai.formula.future.engine import compute_safe_future_envelope
from responsibleai.formula.future.models import (
    CausalRuleFamily,
    ConsequenceKind,
    EnvelopeStatus,
    Reversibility,
)
from responsibleai.formula.future.persistence import compose_persistence
from responsibleai.formula.future.provenance import CausalDerivation, CausalWitnessDag
from responsibleai.formula.future.rules import CausalRule
from responsibleai.formula.graph.kinds import EdgeKind, NodeKind


def _bridge(action: str, target: str, kind: ConsequenceKind, **kw) -> CausalRule:
    return CausalRule(
        rule_id=kw.pop("rule_id", f"b-{action}-{target}"),
        tenant_id="t1",
        family=CausalRuleFamily.CAPABILITY_BRIDGE,
        prerequisite_patterns=(),
        output_kind=kind,
        output_subject_id=kw.pop("subject", "a"),
        output_target_id=target,
        output_scope="local",
        reversibility=kw.pop("reversibility", Reversibility.UNKNOWN),
        epistemic_status=kw.pop("epistemic", EpistemicStatus.INFERRED),
        capability_action=action,
        capability_target_node_id=target,
        persistence=kw.pop("persistence", False),
        information_sensitive=kw.pop("info", False),
    )


def _effect(
    rule_id: str,
    prereqs: tuple[tuple[str, str], ...],
    kind: ConsequenceKind,
    target: str,
    **kw,
) -> CausalRule:
    return CausalRule(
        rule_id=rule_id,
        tenant_id="t1",
        family=kw.pop("family", CausalRuleFamily.DIRECT_EFFECT),
        prerequisite_patterns=prereqs,
        output_kind=kind,
        output_subject_id=kw.pop("subject", "a"),
        output_target_id=target,
        output_scope="local",
        reversibility=kw.pop("reversibility", Reversibility.UNKNOWN),
        epistemic_status=kw.pop("epistemic", EpistemicStatus.INFERRED),
        persistence=kw.pop("persistence", False),
    )


def test_g4_witness_fingerprint_ignores_trajectory_depth() -> None:
    key = ("t1", "a", "x", "STATE_CHANGE", "local")
    base = dict(
        rule_id="r",
        output_key=key,
        prerequisite_keys=(),
        prerequisite_witness_fingerprints=(),
        graph_edge_ids=(),
        causal_depth=1,
        epistemic_status=EpistemicStatus.INFERRED,
        reversibility=Reversibility.UNKNOWN,
        information_sensitive=False,
        subject_id="a",
        persistence=False,
    )
    w1 = CausalDerivation(**base, trajectory_depth=1)
    w2 = CausalDerivation(**base, trajectory_depth=9)
    assert w1.witness_fingerprint() == w2.witness_fingerprint()


def test_g4_same_logical_witness_dedupes_across_horizon_steps() -> None:
    snap = build_snapshot(
        nodes=(node("a", NodeKind.AGENT), node("secret", NodeKind.TOOL)),
        edges=(edge("e1", EdgeKind.CAN_READ, "a", "secret"),),
    )
    closure = compute_capability_closure(snap)
    rules = (
        _bridge("read", "secret", ConsequenceKind.STATE_CHANGE, rule_id="b1"),
        _bridge("read", "secret", ConsequenceKind.STATE_CHANGE, rule_id="b2"),
    )
    env = compute_safe_future_envelope(snap, closure, causal_rules=rules, horizon=4)
    key = ("t1", "a", "secret", "STATE_CHANGE", "local")
    witnesses = [w for w in env.causal_derivations if w.output_key == key]
    assert len(witnesses) == 2
    assert env.status == EnvelopeStatus.COMPLETE


def test_g4_fixed_point_complete_when_no_novel_support() -> None:
    snap = build_snapshot(
        nodes=(node("a", NodeKind.AGENT), node("secret", NodeKind.TOOL)),
        edges=(edge("e1", EdgeKind.CAN_READ, "a", "secret"),),
    )
    closure = compute_capability_closure(snap)
    env = compute_safe_future_envelope(
        snap,
        closure,
        causal_rules=(_bridge("read", "secret", ConsequenceKind.STATE_CHANGE),),
        horizon=6,
    )
    assert env.status == EnvelopeStatus.COMPLETE


def test_g4_horizon_incomplete_when_genuine_frontier_remains() -> None:
    snap = build_snapshot(
        nodes=(node("a", NodeKind.AGENT), node("secret", NodeKind.TOOL), node("svc", NodeKind.API)),
        edges=(
            edge("e1", EdgeKind.CAN_READ, "a", "secret"),
            edge("e2", EdgeKind.CAN_CALL, "secret", "svc"),
        ),
    )
    closure = compute_capability_closure(snap)
    rules = (
        _bridge("read", "secret", ConsequenceKind.STATE_CHANGE),
        _effect(
            "hop1",
            (("STATE_CHANGE", "secret"),),
            ConsequenceKind.RESOURCE_CHANGE,
            "secret",
        ),
        _effect(
            "hop2",
            (("RESOURCE_CHANGE", "secret"),),
            ConsequenceKind.DATA_MUTATION,
            "svc",
        ),
    )
    env = compute_safe_future_envelope(
        snap,
        closure,
        causal_rules=rules,
        budget=FutureEnvelopeBudget(max_horizon_steps=1),
        horizon=1,
    )
    assert env.status == EnvelopeStatus.INCOMPLETE
    assert "horizon_exhausted" in env.blocked_frontier


def test_g4_max_trajectories_not_spent_on_rediscovered_support() -> None:
    snap = build_snapshot(
        nodes=(node("a", NodeKind.AGENT), node("secret", NodeKind.TOOL)),
        edges=(edge("e1", EdgeKind.CAN_READ, "a", "secret"),),
    )
    closure = compute_capability_closure(snap)
    rules = (
        _bridge("read", "secret", ConsequenceKind.STATE_CHANGE, rule_id="b1"),
        _bridge("read", "secret", ConsequenceKind.STATE_CHANGE, rule_id="b2"),
        _effect(
            "self",
            (("STATE_CHANGE", "secret"),),
            ConsequenceKind.STATE_CHANGE,
            "secret",
        ),
    )
    env = compute_safe_future_envelope(
        snap,
        closure,
        causal_rules=rules,
        budget=FutureEnvelopeBudget(max_trajectories=2, max_horizon_steps=4),
        horizon=4,
    )
    assert env.budget_usage["trajectories"] == 2
    assert len(env.causal_derivations) == 2


def test_g4_unrelated_actors_cannot_satisfy_single_subject_rule() -> None:
    snap = build_snapshot(
        nodes=(
            node("a", NodeKind.AGENT),
            node("b", NodeKind.AGENT),
            node("c", NodeKind.AGENT),
            node("ta", NodeKind.TOOL),
            node("tb", NodeKind.TOOL),
        ),
        edges=(
            edge("e1", EdgeKind.CAN_READ, "a", "ta"),
            edge("e2", EdgeKind.CAN_READ, "b", "tb"),
        ),
    )
    closure = compute_capability_closure(snap)
    rules = (
        _bridge("read", "ta", ConsequenceKind.STATE_CHANGE, subject="a", rule_id="ba"),
        _bridge("read", "tb", ConsequenceKind.STATE_CHANGE, subject="b", rule_id="bb"),
        _effect(
            "fabricate",
            (("STATE_CHANGE", "ta"), ("STATE_CHANGE", "tb")),
            ConsequenceKind.DATA_MUTATION,
            "ta",
            subject="c",
        ),
    )
    env = compute_safe_future_envelope(snap, closure, causal_rules=rules, horizon=3)
    assert not any(f.subject_id == "c" for f in env.consequence_facts)


def test_g4_coalition_rule_requires_all_members() -> None:
    snap = build_snapshot(
        nodes=(
            node("a", NodeKind.AGENT),
            node("b", NodeKind.AGENT),
            node("ta", NodeKind.TOOL),
            node("tb", NodeKind.TOOL),
        ),
        edges=(
            edge("e1", EdgeKind.CAN_READ, "a", "ta"),
            edge("e2", EdgeKind.CAN_READ, "b", "tb"),
        ),
    )
    closure = compute_capability_closure(snap)
    coalition = consequence_subject_from_members("t1", ("a", "b"))
    rules = (
        _bridge("read", "ta", ConsequenceKind.STATE_CHANGE, subject="a", rule_id="ba"),
        _bridge("read", "tb", ConsequenceKind.STATE_CHANGE, subject="b", rule_id="bb"),
        _effect(
            "joint",
            (("STATE_CHANGE", "ta"), ("STATE_CHANGE", "tb")),
            ConsequenceKind.MULTI_AGENT_EFFECT,
            "tb",
            subject=coalition,
        ),
    )
    env = compute_safe_future_envelope(snap, closure, causal_rules=rules, horizon=2)
    multi = [
        f for f in env.consequence_facts if f.consequence_kind == ConsequenceKind.MULTI_AGENT_EFFECT
    ]
    assert len(multi) == 1
    assert multi[0].subject_id == "a|b"


def test_g4_coalition_ordering_deterministic() -> None:
    assert consequence_subject_from_members("t1", ("b", "a")) == "a|b"
    assert consequence_subject_from_members("t1", ("a", "b")) == "a|b"


def test_g4_two_distinct_supports_retained() -> None:
    snap = build_snapshot(
        nodes=(node("a", NodeKind.AGENT), node("secret", NodeKind.TOOL)),
        edges=(edge("e1", EdgeKind.CAN_READ, "a", "secret"),),
    )
    closure = compute_capability_closure(snap)
    rules = (
        _bridge("read", "secret", ConsequenceKind.CREDENTIAL_EXPOSURE, rule_id="w1"),
        _bridge(
            "read",
            "secret",
            ConsequenceKind.CREDENTIAL_EXPOSURE,
            rule_id="w2",
            epistemic=EpistemicStatus.DECLARED,
        ),
    )
    env = compute_safe_future_envelope(snap, closure, causal_rules=rules)
    key = env.consequence_facts[0].semantic_key()
    witnesses = [w for w in env.causal_derivations if w.output_key == key]
    assert len(witnesses) == 2


def test_g4_aggregate_epistemic_deterministic() -> None:
    snap = build_snapshot(
        nodes=(node("a", NodeKind.AGENT), node("secret", NodeKind.TOOL)),
        edges=(edge("e1", EdgeKind.CAN_READ, "a", "secret"),),
    )
    closure = compute_capability_closure(snap)
    rules = (
        _bridge(
            "read",
            "secret",
            ConsequenceKind.STATE_CHANGE,
            rule_id="w1",
            epistemic=EpistemicStatus.DECLARED,
        ),
        _bridge(
            "read",
            "secret",
            ConsequenceKind.STATE_CHANGE,
            rule_id="w2",
            epistemic=EpistemicStatus.INFERRED,
        ),
    )
    env = compute_safe_future_envelope(snap, closure, causal_rules=rules)
    fact = next(f for f in env.consequence_facts if f.target_id == "secret")
    assert fact.epistemic_status == EpistemicStatus.INFERRED


def test_g4_aggregate_persistence_conservative() -> None:
    assert compose_persistence(False, True) is True
    assert compose_persistence(False, False) is False
    snap = build_snapshot(
        nodes=(node("a", NodeKind.AGENT), node("secret", NodeKind.TOOL)),
        edges=(edge("e1", EdgeKind.CAN_READ, "a", "secret"),),
    )
    closure = compute_capability_closure(snap)
    rules = (
        _bridge("read", "secret", ConsequenceKind.STATE_CHANGE, rule_id="p0", persistence=False),
        _bridge("read", "secret", ConsequenceKind.STATE_CHANGE, rule_id="p1", persistence=True),
    )
    env = compute_safe_future_envelope(snap, closure, causal_rules=rules)
    fact = next(f for f in env.consequence_facts if f.target_id == "secret")
    assert fact.persistence is True


def test_g4_shuffled_rules_same_envelope_hash() -> None:
    snap = build_snapshot(
        nodes=(node("a", NodeKind.AGENT), node("secret", NodeKind.TOOL), node("svc", NodeKind.API)),
        edges=(
            edge("e1", EdgeKind.CAN_READ, "a", "secret"),
            edge("e2", EdgeKind.CAN_CALL, "secret", "svc"),
        ),
    )
    closure = compute_capability_closure(snap)
    r1 = _bridge("read", "secret", ConsequenceKind.INFORMATION_DISCLOSURE, rule_id="a")
    r2 = _effect("c", (("INFORMATION_DISCLOSURE", "secret"),), ConsequenceKind.DATA_MUTATION, "svc")
    e1 = compute_safe_future_envelope(snap, closure, causal_rules=(r1, r2), horizon=2)
    e2 = compute_safe_future_envelope(snap, closure, causal_rules=(r2, r1), horizon=2)
    assert e1.canonical_hash == e2.canonical_hash


def test_g4_shuffled_witness_insert_order_same_hash() -> None:
    key = ("t1", "a", "x", "STATE_CHANGE", "s")
    w_a = CausalDerivation(
        rule_id="ra",
        output_key=key,
        prerequisite_keys=(),
        prerequisite_witness_fingerprints=(),
        graph_edge_ids=(),
        trajectory_depth=0,
        causal_depth=0,
        epistemic_status=EpistemicStatus.DECLARED,
        reversibility=Reversibility.UNKNOWN,
        information_sensitive=False,
        subject_id="a",
        persistence=False,
    )
    w_b = CausalDerivation(
        rule_id="rb",
        output_key=key,
        prerequisite_keys=(),
        prerequisite_witness_fingerprints=(),
        graph_edge_ids=(),
        trajectory_depth=3,
        causal_depth=0,
        epistemic_status=EpistemicStatus.INFERRED,
        reversibility=Reversibility.REVERSIBLE,
        information_sensitive=False,
        subject_id="a",
        persistence=True,
    )
    dag1 = CausalWitnessDag()
    dag2 = CausalWitnessDag()
    dag1.add_witness(w_a)
    dag1.add_witness(w_b)
    dag2.add_witness(w_b)
    dag2.add_witness(w_a)
    fps1 = tuple(w.witness_fingerprint() for w in dag1.all_witnesses())
    fps2 = tuple(w.witness_fingerprint() for w in dag2.all_witnesses())
    assert fps1 == fps2
