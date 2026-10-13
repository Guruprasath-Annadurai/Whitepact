# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""Gate 4 semantic remediation regressions (ChatGPT P1 blockers)."""

from __future__ import annotations

from tests.formula.helpers_gate3 import build_snapshot, edge, node

from responsibleai.formula.capability import CapabilityClosureBudget, compute_capability_closure
from responsibleai.formula.capability.budget import ClosureStatus
from responsibleai.formula.capability.joint import JointCapabilityRule
from responsibleai.formula.epistemic import EpistemicStatus
from responsibleai.formula.future.budget import FutureEnvelopeBudget
from responsibleai.formula.future.engine import compute_safe_future_envelope
from responsibleai.formula.future.models import (
    CausalRuleFamily,
    ConsequenceKind,
    ConsequenceReachability,
    EnvelopeStatus,
    Reversibility,
)
from responsibleai.formula.future.query import query_consequence_reachability
from responsibleai.formula.future.reversibility import compose_reversibility
from responsibleai.formula.future.rules import CausalRule
from responsibleai.formula.future.serialize import causal_rules_fingerprint
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
        information_sensitive=kw.pop("info", False),
    )


def _chain(
    rule_id: str, prereq: tuple[str, str], kind: ConsequenceKind, target: str, **kw
) -> CausalRule:
    return CausalRule(
        rule_id=rule_id,
        tenant_id="t1",
        family=kw.pop("family", CausalRuleFamily.DIRECT_EFFECT),
        prerequisite_patterns=(prereq,),
        output_kind=kind,
        output_subject_id=kw.pop("subject", "a"),
        output_target_id=target,
        output_scope="local",
        reversibility=kw.pop("reversibility", Reversibility.UNKNOWN),
        epistemic_status=kw.pop("epistemic", EpistemicStatus.INFERRED),
        graph_edge_id=kw.pop("edge_id", None),
        information_sensitive=kw.pop("info", False),
        recovery_rule=kw.pop("recovery", False),
    )


def _snap():
    snap = build_snapshot(
        nodes=(node("a", NodeKind.AGENT), node("secret", NodeKind.TOOL), node("svc", NodeKind.API)),
        edges=(
            edge("e1", EdgeKind.CAN_READ, "a", "secret"),
            edge("e2", EdgeKind.CAN_CALL, "secret", "svc"),
        ),
    )
    return snap


def test_r01_incomplete_closure_forces_incomplete_envelope() -> None:
    snap = _snap()
    closure = compute_capability_closure(snap, budget=CapabilityClosureBudget(max_facts=1))
    assert closure.status == ClosureStatus.INCOMPLETE
    env = compute_safe_future_envelope(
        snap, closure, causal_rules=(_bridge("read", "secret", ConsequenceKind.STATE_CHANGE),)
    )
    assert env.status == EnvelopeStatus.INCOMPLETE
    assert "capability_closure_incomplete" in env.blocked_frontier


def test_r02_incomplete_closure_still_derives_known_consequence() -> None:
    snap = _snap()
    closure = compute_capability_closure(snap, budget=CapabilityClosureBudget(max_facts=1))
    env = compute_safe_future_envelope(
        snap, closure, causal_rules=(_bridge("read", "secret", ConsequenceKind.STATE_CHANGE),)
    )
    assert env.consequence_facts


def test_r03_max_path_depth_exact_boundary() -> None:
    snap = _snap()
    closure = compute_capability_closure(snap)
    rules = (
        _bridge("read", "secret", ConsequenceKind.STATE_CHANGE, rule_id="s"),
        _chain("c1", ("STATE_CHANGE", "secret"), ConsequenceKind.RESOURCE_CHANGE, "svc"),
        _chain("c2", ("RESOURCE_CHANGE", "svc"), ConsequenceKind.DATA_MUTATION, "svc"),
    )
    ok = compute_safe_future_envelope(
        snap, closure, causal_rules=rules, budget=FutureEnvelopeBudget(max_path_depth=2), horizon=3
    )
    blocked = compute_safe_future_envelope(
        snap, closure, causal_rules=rules, budget=FutureEnvelopeBudget(max_path_depth=1), horizon=3
    )
    assert len(ok.consequence_facts) >= len(blocked.consequence_facts)
    assert blocked.status == EnvelopeStatus.INCOMPLETE


def test_r04_max_trajectories_boundary() -> None:
    snap = _snap()
    closure = compute_capability_closure(snap)
    rules = (
        _bridge("read", "secret", ConsequenceKind.CREDENTIAL_EXPOSURE, rule_id="s"),
        _chain("a", ("CREDENTIAL_EXPOSURE", "secret"), ConsequenceKind.DATA_MUTATION, "secret"),
        _chain("b", ("CREDENTIAL_EXPOSURE", "secret"), ConsequenceKind.DATA_DELETION, "secret"),
    )
    env = compute_safe_future_envelope(
        snap,
        closure,
        causal_rules=rules,
        budget=FutureEnvelopeBudget(max_trajectories=1, max_horizon_steps=2),
        horizon=2,
    )
    assert env.status == EnvelopeStatus.INCOMPLETE
    assert len(env.causal_derivations) <= 1


def test_r05_max_states_never_overshoots() -> None:
    snap = _snap()
    closure = compute_capability_closure(snap)
    env = compute_safe_future_envelope(
        snap,
        closure,
        causal_rules=(_bridge("read", "secret", ConsequenceKind.STATE_CHANGE),),
        budget=FutureEnvelopeBudget(max_states=2, max_horizon_steps=4),
        horizon=4,
    )
    assert len(env.reachable_states) <= 2


def test_r08_unknown_plus_reversible_is_unknown() -> None:
    assert (
        compose_reversibility(Reversibility.REVERSIBLE, Reversibility.UNKNOWN)
        == Reversibility.UNKNOWN
    )


def test_r09_irreversible_dominates() -> None:
    assert (
        compose_reversibility(Reversibility.REVERSIBLE, Reversibility.IRREVERSIBLE)
        == Reversibility.IRREVERSIBLE
    )


def test_r11_sensitive_multi_hop() -> None:
    snap = _snap()
    closure = compute_capability_closure(snap)
    rules = (
        _bridge("read", "secret", ConsequenceKind.SECRET_DISCLOSURE, info=True, rule_id="s"),
        _chain(
            "hop",
            ("SECRET_DISCLOSURE", "secret"),
            ConsequenceKind.PII_DISCLOSURE,
            "svc",
        ),
    )
    env = compute_safe_future_envelope(snap, closure, causal_rules=rules, horizon=2)
    pii = next(
        f for f in env.consequence_facts if f.consequence_kind == ConsequenceKind.PII_DISCLOSURE
    )
    assert pii.information_sensitive
    assert pii.reversibility == Reversibility.IRREVERSIBLE


def test_r12_two_witnesses_same_semantic_fact() -> None:
    snap = _snap()
    closure = compute_capability_closure(snap)
    rules = (
        _bridge(
            "read",
            "secret",
            ConsequenceKind.STATE_CHANGE,
            rule_id="b1",
            epistemic=EpistemicStatus.DECLARED,
        ),
        _bridge(
            "read",
            "secret",
            ConsequenceKind.STATE_CHANGE,
            rule_id="b2",
            epistemic=EpistemicStatus.INFERRED,
        ),
    )
    env = compute_safe_future_envelope(snap, closure, causal_rules=rules, horizon=1)
    key = next(
        f.semantic_key()
        for f in env.consequence_facts
        if f.consequence_kind == ConsequenceKind.STATE_CHANGE and f.target_id == "secret"
    )
    witnesses = [w for w in env.causal_derivations if w.output_key == key]
    assert len(witnesses) == 2
    assert len({w.witness_fingerprint() for w in witnesses}) == 2


def test_r16_shuffled_rules_identical_hash() -> None:
    snap = _snap()
    closure = compute_capability_closure(snap)
    r1 = _bridge("read", "secret", ConsequenceKind.INFORMATION_DISCLOSURE, rule_id="a")
    r2 = _chain("c", ("INFORMATION_DISCLOSURE", "secret"), ConsequenceKind.DATA_MUTATION, "svc")
    a = compute_safe_future_envelope(snap, closure, causal_rules=(r1, r2), horizon=2)
    b = compute_safe_future_envelope(snap, closure, causal_rules=(r2, r1), horizon=2)
    assert a.canonical_hash == b.canonical_hash


def test_r19_unrelated_edge_not_borrowed() -> None:
    snap = _snap()
    closure = compute_capability_closure(snap)
    rules = (
        _bridge("read", "secret", ConsequenceKind.STATE_CHANGE, rule_id="s"),
        _chain(
            "bad",
            ("STATE_CHANGE", "svc"),
            ConsequenceKind.EXTERNAL_SIDE_EFFECT,
            "svc",
            family=CausalRuleFamily.PROPAGATED_EFFECT,
            edge_id="e2",
        ),
    )
    env = compute_safe_future_envelope(snap, closure, causal_rules=rules, horizon=2)
    assert not any(
        f.consequence_kind == ConsequenceKind.EXTERNAL_SIDE_EFFECT for f in env.consequence_facts
    )


def test_r20_edge_propagation_when_anchored() -> None:
    snap = _snap()
    closure = compute_capability_closure(snap)
    rules = (
        _bridge("read", "secret", ConsequenceKind.CREDENTIAL_EXPOSURE, rule_id="s"),
        _chain(
            "good",
            ("CREDENTIAL_EXPOSURE", "secret"),
            ConsequenceKind.EXTERNAL_SIDE_EFFECT,
            "svc",
            family=CausalRuleFamily.PROPAGATED_EFFECT,
            edge_id="e2",
        ),
    )
    env = compute_safe_future_envelope(snap, closure, causal_rules=rules, horizon=2)
    assert any(
        f.consequence_kind == ConsequenceKind.EXTERNAL_SIDE_EFFECT for f in env.consequence_facts
    )


def test_r21_joint_actor_survives_bridge() -> None:
    snap = build_snapshot(
        nodes=(
            node("a", NodeKind.AGENT),
            node("b", NodeKind.AGENT),
            node("t", NodeKind.TOOL),
            node("db", NodeKind.DATABASE),
        ),
        edges=(
            edge("e1", EdgeKind.CAN_READ, "a", "t"),
            edge("e2", EdgeKind.CAN_WRITE, "b", "db"),
        ),
    )
    base = compute_capability_closure(snap)
    pa = next(f.semantic_key() for f in base.facts if f.actor.member_ids == ("a",))
    pb = next(
        f.semantic_key() for f in base.facts if f.actor.member_ids == ("b",) and f.action == "write"
    )
    joint = (
        JointCapabilityRule(
            rule_id="joint",
            tenant_id="t1",
            required_semantic_keys=(pa, pb),
            coalition_member_ids=("a", "b"),
            action="write",
            target_node_id="db",
        ),
    )
    closure = compute_capability_closure(snap, joint_rules=joint)
    env = compute_safe_future_envelope(
        snap, closure, causal_rules=(_bridge("write", "db", ConsequenceKind.MULTI_AGENT_EFFECT),)
    )
    fact = env.consequence_facts[0]
    assert fact.subject_id == "a|b"


def test_r22_coalition_member_order_canonical() -> None:
    snap = build_snapshot(
        nodes=(
            node("a", NodeKind.AGENT),
            node("b", NodeKind.AGENT),
            node("t", NodeKind.TOOL),
            node("db", NodeKind.DATABASE),
        ),
        edges=(
            edge("e1", EdgeKind.CAN_READ, "a", "t"),
            edge("e2", EdgeKind.CAN_WRITE, "b", "db"),
        ),
    )
    base = compute_capability_closure(snap)
    pa = next(f.semantic_key() for f in base.facts if f.actor.member_ids == ("a",))
    pb = next(
        f.semantic_key() for f in base.facts if f.actor.member_ids == ("b",) and f.action == "write"
    )
    j1 = JointCapabilityRule(
        rule_id="j1",
        tenant_id="t1",
        required_semantic_keys=(pa, pb),
        coalition_member_ids=("b", "a"),
        action="write",
        target_node_id="db",
    )
    j2 = JointCapabilityRule(
        rule_id="j2",
        tenant_id="t1",
        required_semantic_keys=(pa, pb),
        coalition_member_ids=("a", "b"),
        action="write",
        target_node_id="db",
    )
    c1 = compute_capability_closure(snap, joint_rules=(j1,))
    c2 = compute_capability_closure(snap, joint_rules=(j2,))
    e1 = compute_safe_future_envelope(
        snap, c1, causal_rules=(_bridge("write", "db", ConsequenceKind.STATE_CHANGE),)
    )
    e2 = compute_safe_future_envelope(
        snap, c2, causal_rules=(_bridge("write", "db", ConsequenceKind.STATE_CHANGE),)
    )
    assert e1.consequence_facts[0].subject_id == e2.consequence_facts[0].subject_id == "a|b"


def test_r24_converged_applicable_rule_complete() -> None:
    snap = _snap()
    closure = compute_capability_closure(snap)
    rules = (_bridge("read", "secret", ConsequenceKind.STATE_CHANGE, rule_id="s"),)
    env = compute_safe_future_envelope(snap, closure, causal_rules=rules, horizon=4)
    assert env.status == EnvelopeStatus.COMPLETE


def test_r25_genuine_successor_incomplete() -> None:
    snap = _snap()
    closure = compute_capability_closure(snap)
    rules = (
        _bridge("read", "secret", ConsequenceKind.STATE_CHANGE, rule_id="s"),
        _chain("hop1", ("STATE_CHANGE", "secret"), ConsequenceKind.RESOURCE_CHANGE, "secret"),
        _chain("hop2", ("RESOURCE_CHANGE", "secret"), ConsequenceKind.DATA_MUTATION, "svc"),
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


def test_r26_absent_complete_not_derived() -> None:
    snap = _snap()
    closure = compute_capability_closure(snap)
    env = compute_safe_future_envelope(snap, closure, causal_rules=())
    key = ("t1", "a", "missing", "STATE_CHANGE", "local")
    assert query_consequence_reachability(env, key) == ConsequenceReachability.NOT_DERIVED


def test_r27_absent_incomplete_unknown() -> None:
    snap = _snap()
    closure = compute_capability_closure(snap, budget=CapabilityClosureBudget(max_facts=1))
    env = compute_safe_future_envelope(snap, closure, causal_rules=())
    key = ("t1", "a", "missing", "STATE_CHANGE", "local")
    assert query_consequence_reachability(env, key) == ConsequenceReachability.UNKNOWN


def test_r28_persistence_changes_rule_fingerprint() -> None:
    base = dict(
        rule_id="r",
        tenant_id="t1",
        family=CausalRuleFamily.CAPABILITY_BRIDGE,
        prerequisite_patterns=(),
        output_kind=ConsequenceKind.STATE_CHANGE,
        output_subject_id="a",
        output_target_id="t",
        output_scope="s",
        reversibility=Reversibility.UNKNOWN,
        epistemic_status=EpistemicStatus.UNKNOWN,
        capability_action="read",
        capability_target_node_id="t",
    )
    a = causal_rules_fingerprint((CausalRule(**base, persistence=False),))
    b = causal_rules_fingerprint((CausalRule(**base, persistence=True),))
    assert a != b


def test_r29_information_sensitive_changes_fingerprint() -> None:
    base = dict(
        rule_id="r",
        tenant_id="t1",
        family=CausalRuleFamily.CAPABILITY_BRIDGE,
        prerequisite_patterns=(),
        output_kind=ConsequenceKind.STATE_CHANGE,
        output_subject_id="a",
        output_target_id="t",
        output_scope="s",
        reversibility=Reversibility.UNKNOWN,
        epistemic_status=EpistemicStatus.UNKNOWN,
        capability_action="read",
        capability_target_node_id="t",
    )
    a = causal_rules_fingerprint((CausalRule(**base, information_sensitive=False),))
    b = causal_rules_fingerprint((CausalRule(**base, information_sensitive=True),))
    assert a != b


def test_r33_no_authority_in_envelope() -> None:
    snap = _snap()
    closure = compute_capability_closure(snap)
    env = compute_safe_future_envelope(
        snap, closure, causal_rules=(_bridge("read", "secret", ConsequenceKind.STATE_CHANGE),)
    )
    blob = str(env)
    assert "authorized" not in blob.lower()
