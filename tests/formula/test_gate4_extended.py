# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""Gate 4 extended property matrix (P3–P30 coverage gaps)."""

from __future__ import annotations

import pytest
from tests.formula.helpers_gate3 import build_snapshot, edge, node

from responsibleai.formula.capability import compute_capability_closure
from responsibleai.formula.epistemic import EpistemicStatus
from responsibleai.formula.errors import InvalidCausalRule
from responsibleai.formula.future.budget import FutureEnvelopeBudget
from responsibleai.formula.future.engine import compute_safe_future_envelope
from responsibleai.formula.future.models import (
    CausalRuleFamily,
    ConsequenceKind,
    EnvelopeStatus,
    Reversibility,
)
from responsibleai.formula.future.rules import CausalRule
from responsibleai.formula.graph.kinds import EdgeKind, NodeKind


def _bridge(action: str, target: str, kind: ConsequenceKind, **kw) -> CausalRule:
    return CausalRule(
        rule_id=kw.pop("rule_id", f"bridge-{action}-{target}-{kind.value}"),
        tenant_id="t1",
        family=CausalRuleFamily.CAPABILITY_BRIDGE,
        prerequisite_patterns=(),
        output_kind=kind,
        output_subject_id=kw.pop("subject", "a"),
        output_target_id=target,
        output_scope=kw.pop("scope", "local"),
        reversibility=kw.pop("reversibility", Reversibility.UNKNOWN),
        epistemic_status=kw.pop("epistemic", EpistemicStatus.INFERRED),
        capability_action=action,
        capability_target_node_id=target,
        information_sensitive=kw.pop("info", False),
        recovery_rule=kw.pop("recovery", False),
    )


def _chain(
    rule_id: str,
    prereq: tuple[str, str],
    out_kind: ConsequenceKind,
    out_target: str,
    **kw,
) -> CausalRule:
    return CausalRule(
        rule_id=rule_id,
        tenant_id="t1",
        family=kw.pop("family", CausalRuleFamily.DIRECT_EFFECT),
        prerequisite_patterns=(prereq,),
        output_kind=out_kind,
        output_subject_id="a",
        output_target_id=out_target,
        output_scope="local",
        reversibility=kw.pop("reversibility", Reversibility.UNKNOWN),
        epistemic_status=kw.pop("epistemic", EpistemicStatus.INFERRED),
        graph_edge_id=kw.pop("edge_id", None),
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
    return snap, compute_capability_closure(snap)


def test_p3_alternate_trajectories() -> None:
    snap, closure = _snap()
    rules = (
        _bridge("read", "secret", ConsequenceKind.CREDENTIAL_EXPOSURE, rule_id="b1"),
        _chain("alt-a", ("CREDENTIAL_EXPOSURE", "secret"), ConsequenceKind.DATA_MUTATION, "secret"),
        _chain(
            "alt-b", ("CREDENTIAL_EXPOSURE", "secret"), ConsequenceKind.SERVICE_DISRUPTION, "svc"
        ),
    )
    env = compute_safe_future_envelope(snap, closure, causal_rules=rules, horizon=2)
    kinds = {f.consequence_kind for f in env.consequence_facts}
    assert ConsequenceKind.DATA_MUTATION in kinds
    assert ConsequenceKind.SERVICE_DISRUPTION in kinds


def test_p4_causal_cycle_terminates_in_engine() -> None:
    snap, closure = _snap()
    rules = (
        _bridge("read", "secret", ConsequenceKind.STATE_CHANGE, rule_id="seed"),
        _chain("ab", ("STATE_CHANGE", "secret"), ConsequenceKind.STATE_CHANGE, "svc"),
        _chain("ba", ("STATE_CHANGE", "svc"), ConsequenceKind.STATE_CHANGE, "secret"),
    )
    env = compute_safe_future_envelope(snap, closure, causal_rules=rules, horizon=4)
    assert len(env.consequence_facts) >= 2


def test_p5_shallow_and_deep_trajectories() -> None:
    snap, closure = _snap()
    rules = (
        _bridge("read", "secret", ConsequenceKind.CREDENTIAL_EXPOSURE, rule_id="seed"),
        _chain(
            "deep", ("CREDENTIAL_EXPOSURE", "secret"), ConsequenceKind.EXTERNAL_SIDE_EFFECT, "svc"
        ),
    )
    shallow = compute_safe_future_envelope(snap, closure, causal_rules=rules, horizon=1)
    deep = compute_safe_future_envelope(snap, closure, causal_rules=rules, horizon=3)
    assert len(deep.consequence_facts) >= len(shallow.consequence_facts)


def test_p7_state_budget_incomplete() -> None:
    snap, closure = _snap()
    rules = (_bridge("read", "secret", ConsequenceKind.STATE_CHANGE, rule_id="s"),)
    env = compute_safe_future_envelope(
        snap,
        closure,
        causal_rules=rules,
        budget=FutureEnvelopeBudget(max_states=1, max_horizon_steps=4),
        horizon=4,
    )
    assert env.status == EnvelopeStatus.INCOMPLETE
    assert "max_states" in env.blocked_frontier


def test_p8_derivation_budget_incomplete() -> None:
    snap, closure = _snap()
    rules = (
        _bridge("read", "secret", ConsequenceKind.STATE_CHANGE, rule_id="s"),
        _chain("x", ("STATE_CHANGE", "secret"), ConsequenceKind.RESOURCE_CHANGE, "svc"),
    )
    env = compute_safe_future_envelope(
        snap,
        closure,
        causal_rules=rules,
        budget=FutureEnvelopeBudget(max_derivations=1, max_horizon_steps=4),
        horizon=4,
    )
    assert env.status == EnvelopeStatus.INCOMPLETE


def test_p9_rule_application_budget_incomplete() -> None:
    snap, closure = _snap()
    rules = (
        _bridge("read", "secret", ConsequenceKind.CREDENTIAL_EXPOSURE, rule_id="s"),
        _chain("a", ("CREDENTIAL_EXPOSURE", "secret"), ConsequenceKind.DATA_MUTATION, "secret"),
        _chain("b", ("CREDENTIAL_EXPOSURE", "secret"), ConsequenceKind.DATA_DELETION, "secret"),
    )
    env = compute_safe_future_envelope(
        snap,
        closure,
        causal_rules=rules,
        budget=FutureEnvelopeBudget(max_rule_applications=1, max_horizon_steps=3),
        horizon=3,
    )
    assert env.status == EnvelopeStatus.INCOMPLETE


def test_p14_monotone_horizon() -> None:
    snap, closure = _snap()
    rules = (
        _bridge("read", "secret", ConsequenceKind.CREDENTIAL_EXPOSURE, rule_id="s"),
        _chain(
            "c1", ("CREDENTIAL_EXPOSURE", "secret"), ConsequenceKind.EXTERNAL_SIDE_EFFECT, "svc"
        ),
    )
    small = compute_safe_future_envelope(snap, closure, causal_rules=rules, horizon=1)
    large = compute_safe_future_envelope(snap, closure, causal_rules=rules, horizon=4)
    assert len(large.consequence_facts) >= len(small.consequence_facts)


def test_p17_reversible_effect() -> None:
    snap, closure = _snap()
    rules = (
        _bridge(
            "read", "secret", ConsequenceKind.STATE_CHANGE, reversibility=Reversibility.REVERSIBLE
        ),
    )
    env = compute_safe_future_envelope(snap, closure, causal_rules=rules)
    fact = env.consequence_facts[0]
    assert fact.reversibility == Reversibility.REVERSIBLE


def test_p18_irreversible_effect() -> None:
    snap, closure = _snap()
    rules = (
        _bridge(
            "read",
            "secret",
            ConsequenceKind.DATA_DELETION,
            reversibility=Reversibility.IRREVERSIBLE,
        ),
    )
    env = compute_safe_future_envelope(snap, closure, causal_rules=rules)
    assert env.consequence_facts[0].reversibility == Reversibility.IRREVERSIBLE


def test_p19_conditional_reversibility_recovery() -> None:
    snap, closure = _snap()
    rules = (
        _bridge(
            "read",
            "secret",
            ConsequenceKind.DATA_MUTATION,
            reversibility=Reversibility.IRREVERSIBLE,
            rule_id="s",
        ),
        _chain(
            "rec",
            ("DATA_MUTATION", "secret"),
            ConsequenceKind.STATE_CHANGE,
            "secret",
            reversibility=Reversibility.REVERSIBLE,
            recovery=True,
        ),
    )
    env = compute_safe_future_envelope(snap, closure, causal_rules=rules, horizon=2)
    mut = next(
        f for f in env.consequence_facts if f.consequence_kind == ConsequenceKind.DATA_MUTATION
    )
    assert mut.reversibility == Reversibility.IRREVERSIBLE


def test_p21_credential_exposure_propagation() -> None:
    snap, closure = _snap()
    rules = (
        _bridge("read", "secret", ConsequenceKind.CREDENTIAL_EXPOSURE, rule_id="s"),
        _chain(
            "prop",
            ("CREDENTIAL_EXPOSURE", "secret"),
            ConsequenceKind.CREDENTIAL_DISCLOSURE,
            "svc",
            family=CausalRuleFamily.CREDENTIAL_PROPAGATION,
            edge_id="e2",
        ),
    )
    env = compute_safe_future_envelope(snap, closure, causal_rules=rules, horizon=2)
    assert ConsequenceKind.CREDENTIAL_DISCLOSURE in {
        f.consequence_kind for f in env.consequence_facts
    }


def test_p22_multi_agent_propagation() -> None:
    snap = build_snapshot(
        nodes=(node("a", NodeKind.AGENT), node("b", NodeKind.AGENT), node("t", NodeKind.TOOL)),
        edges=(edge("e1", EdgeKind.CAN_CALL, "a", "t"), edge("e2", EdgeKind.CAN_CALL, "b", "t")),
    )
    closure = compute_capability_closure(snap)
    rules = (
        _bridge("call", "t", ConsequenceKind.MULTI_AGENT_EFFECT, rule_id="s"),
        _chain(
            "relay",
            ("MULTI_AGENT_EFFECT", "t"),
            ConsequenceKind.IDENTITY_EFFECT,
            "t",
            family=CausalRuleFamily.MULTI_AGENT_PROPAGATION,
        ),
    )
    env = compute_safe_future_envelope(snap, closure, causal_rules=rules, horizon=2)
    assert ConsequenceKind.IDENTITY_EFFECT in {f.consequence_kind for f in env.consequence_facts}


def test_p23_blast_radius_aggregation() -> None:
    snap, closure = _snap()
    rules = (
        _bridge("read", "secret", ConsequenceKind.STATE_CHANGE, rule_id="s"),
        _chain("x", ("STATE_CHANGE", "secret"), ConsequenceKind.EXTERNAL_SIDE_EFFECT, "svc"),
    )
    env = compute_safe_future_envelope(snap, closure, causal_rules=rules, horizon=2)
    assert "a" in env.blast_radius.affected_actors
    assert env.blast_radius.propagation_depth >= 1


def test_p24_external_system_effect() -> None:
    snap, closure = _snap()
    rules = (_bridge("read", "secret", ConsequenceKind.EXTERNAL_SIDE_EFFECT, rule_id="s"),)
    env = compute_safe_future_envelope(snap, closure, causal_rules=rules)
    assert env.blast_radius.external_targets


def test_p26_unknown_evidence_remains_unknown() -> None:
    snap, closure = _snap()
    rules = (
        _bridge("read", "secret", ConsequenceKind.STATE_CHANGE, epistemic=EpistemicStatus.UNKNOWN),
    )
    env = compute_safe_future_envelope(snap, closure, causal_rules=rules)
    assert env.consequence_facts[0].epistemic_status == EpistemicStatus.UNKNOWN


def test_p27_semantic_state_deduplication() -> None:
    snap, closure = _snap()
    rules = (
        _bridge("read", "secret", ConsequenceKind.STATE_CHANGE, rule_id="s1"),
        _bridge("read", "secret", ConsequenceKind.STATE_CHANGE, rule_id="s2"),
    )
    env = compute_safe_future_envelope(snap, closure, causal_rules=rules)
    assert len(env.consequence_facts) == 1


def test_p28_shuffled_rules_same_hash() -> None:
    snap, closure = _snap()
    r1 = _bridge("read", "secret", ConsequenceKind.INFORMATION_DISCLOSURE, rule_id="a")
    r2 = _chain("c", ("INFORMATION_DISCLOSURE", "secret"), ConsequenceKind.DATA_MUTATION, "svc")
    env_a = compute_safe_future_envelope(snap, closure, causal_rules=(r1, r2), horizon=2)
    env_b = compute_safe_future_envelope(snap, closure, causal_rules=(r2, r1), horizon=2)
    assert env_a.canonical_hash == env_b.canonical_hash


def test_duplicate_rule_id_rejected() -> None:
    snap, closure = _snap()
    r = _bridge("read", "secret", ConsequenceKind.STATE_CHANGE, rule_id="dup")
    with pytest.raises(InvalidCausalRule):
        compute_safe_future_envelope(snap, closure, causal_rules=(r, r))


def test_budget_validate_positive() -> None:
    with pytest.raises(InvalidCausalRule):
        FutureEnvelopeBudget(max_horizon_steps=0).validate()
