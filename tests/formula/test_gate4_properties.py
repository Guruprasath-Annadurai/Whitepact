# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""Gate 4 — Safe Future Envelope property and adversarial tests."""

from __future__ import annotations

import pytest
from tests.formula.helpers_gate3 import build_snapshot, edge, node

from responsibleai.formula.capability import compute_capability_closure
from responsibleai.formula.capability.budget import CapabilityClosureBudget
from responsibleai.formula.epistemic import EpistemicStatus
from responsibleai.formula.errors import (
    CausalCycleError,
    CausalTenantMismatch,
    InvalidCausalRule,
)
from responsibleai.formula.future.budget import FutureEnvelopeBudget
from responsibleai.formula.future.engine import compute_safe_future_envelope
from responsibleai.formula.future.invariants import validate_gate4_invariants
from responsibleai.formula.future.models import (
    CausalRuleFamily,
    ConsequenceKind,
    EnvelopeStatus,
    Reversibility,
)
from responsibleai.formula.future.provenance import CausalDerivation, CausalWitnessDag
from responsibleai.formula.future.rules import CausalRule
from responsibleai.formula.future.serialize import serialize_envelope
from responsibleai.formula.graph.kinds import EdgeKind, NodeKind


def _bridge(action: str, target: str, kind: ConsequenceKind, **kw) -> CausalRule:
    return CausalRule(
        rule_id=kw.pop("rule_id", f"bridge-{action}-{target}"),
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
    )


def _chain(
    rule_id: str,
    prereq: tuple[str, str],
    out_kind: ConsequenceKind,
    out_target: str,
    *,
    edge_id: str | None = None,
) -> CausalRule:
    return CausalRule(
        rule_id=rule_id,
        tenant_id="t1",
        family=CausalRuleFamily.PROPAGATED_EFFECT if edge_id else CausalRuleFamily.DIRECT_EFFECT,
        prerequisite_patterns=(prereq,),
        output_kind=out_kind,
        output_subject_id="a",
        output_target_id=out_target if not edge_id else "*",
        output_scope="local",
        reversibility=Reversibility.UNKNOWN,
        epistemic_status=EpistemicStatus.INFERRED,
        graph_edge_id=edge_id,
    )


def _base_closure():
    snap = build_snapshot(
        nodes=(node("a", NodeKind.AGENT), node("secret", NodeKind.TOOL), node("svc", NodeKind.API)),
        edges=(
            edge("e1", EdgeKind.CAN_READ, "a", "secret"),
            edge("e2", EdgeKind.CAN_CALL, "secret", "svc"),
        ),
    )
    closure = compute_capability_closure(snap)
    return snap, closure


def test_p1_direct_consequence() -> None:
    snap, closure = _base_closure()
    rules = (_bridge("read", "secret", ConsequenceKind.INFORMATION_DISCLOSURE, info=True),)
    env = compute_safe_future_envelope(snap, closure, causal_rules=rules)
    assert any(
        f.consequence_kind == ConsequenceKind.INFORMATION_DISCLOSURE for f in env.consequence_facts
    )
    assert validate_gate4_invariants(env) == []


def test_p2_multi_step_chain() -> None:
    snap, closure = _base_closure()
    rules = (
        _bridge("read", "secret", ConsequenceKind.CREDENTIAL_EXPOSURE),
        _chain(
            "prop",
            ("CREDENTIAL_EXPOSURE", "secret"),
            ConsequenceKind.EXTERNAL_SIDE_EFFECT,
            "svc",
            edge_id="e2",
        ),
    )
    env = compute_safe_future_envelope(snap, closure, causal_rules=rules, horizon=3)
    kinds = {f.consequence_kind for f in env.consequence_facts}
    assert ConsequenceKind.CREDENTIAL_EXPOSURE in kinds
    assert ConsequenceKind.EXTERNAL_SIDE_EFFECT in kinds


def test_p6_horizon_truncation_incomplete() -> None:
    snap, closure = _base_closure()
    rules = (
        _bridge("read", "secret", ConsequenceKind.STATE_CHANGE),
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


def test_p10_epistemic_weakest_link() -> None:
    snap, closure = _base_closure()
    rules = (
        _bridge(
            "read", "secret", ConsequenceKind.DATA_MUTATION, epistemic=EpistemicStatus.VERIFIED
        ),
    )
    env = compute_safe_future_envelope(snap, closure, causal_rules=rules)
    assert env.epistemic_summary in (
        EpistemicStatus.VERIFIED,
        EpistemicStatus.INFERRED,
        EpistemicStatus.DECLARED,
        EpistemicStatus.UNKNOWN,
    )


def test_p11_tenant_mismatch() -> None:
    snap, closure = _base_closure()
    bad = CausalRule(
        rule_id="bad",
        tenant_id="other",
        family=CausalRuleFamily.CAPABILITY_BRIDGE,
        prerequisite_patterns=(),
        output_kind=ConsequenceKind.STATE_CHANGE,
        output_subject_id="a",
        output_target_id="secret",
        output_scope="x",
        reversibility=Reversibility.UNKNOWN,
        epistemic_status=EpistemicStatus.UNKNOWN,
        capability_action="read",
        capability_target_node_id="secret",
    )
    with pytest.raises(CausalTenantMismatch):
        compute_safe_future_envelope(snap, closure, causal_rules=(bad,))


def test_p12_deterministic_hash() -> None:
    snap, closure = _base_closure()
    rules = (_bridge("read", "secret", ConsequenceKind.INFORMATION_DISCLOSURE),)
    a = compute_safe_future_envelope(snap, closure, causal_rules=rules)
    b = compute_safe_future_envelope(snap, closure, causal_rules=rules)
    assert a.canonical_hash == b.canonical_hash


def test_p13_idempotence() -> None:
    snap, closure = _base_closure()
    rules = (_bridge("read", "secret", ConsequenceKind.INFORMATION_DISCLOSURE),)
    env = compute_safe_future_envelope(snap, closure, causal_rules=rules)
    again = compute_safe_future_envelope(snap, closure, causal_rules=rules)
    assert serialize_envelope(env) == serialize_envelope(again)


def test_p15_no_authority_fields() -> None:
    snap, closure = _base_closure()
    env = compute_safe_future_envelope(
        snap, closure, causal_rules=(_bridge("read", "secret", ConsequenceKind.STATE_CHANGE),)
    )
    blob = str(serialize_envelope(env))
    assert "authorized" not in blob.lower()
    assert "grant" not in blob.lower()


def _witness(
    rule_id: str,
    output_key: tuple[str, str, str, str, str],
    prereqs: tuple = (),
    prereq_fps: tuple = (),
    depth: int = 1,
) -> CausalDerivation:
    return CausalDerivation(
        rule_id=rule_id,
        output_key=output_key,
        prerequisite_keys=prereqs,
        prerequisite_witness_fingerprints=prereq_fps,
        graph_edge_ids=(),
        trajectory_depth=depth,
        causal_depth=depth,
        epistemic_status=EpistemicStatus.UNKNOWN,
        reversibility=Reversibility.UNKNOWN,
        information_sensitive=False,
        subject_id=output_key[1],
        persistence=False,
    )


def test_p16_provenance_cycle_rejected() -> None:
    dag = CausalWitnessDag()
    k_a = ("t1", "a", "x", "STATE_CHANGE", "s")
    k_b = ("t1", "a", "y", "STATE_CHANGE", "s")
    dag.add_witness(_witness("r1", k_a))
    w_a = dag.get_witness(k_a)
    assert w_a is not None
    dag.add_witness(_witness("r2", k_b, (k_a,), (w_a.witness_fingerprint(),), 2))
    with pytest.raises(CausalCycleError):
        w_b = dag.get_witness(k_b)
        assert w_b is not None
        dag.add_witness(_witness("r3", k_a, (k_b,), (w_b.witness_fingerprint(),), 3))


def test_p20_information_hazard_irreversible() -> None:
    snap, closure = _base_closure()
    rules = (
        _bridge(
            "read",
            "secret",
            ConsequenceKind.PII_DISCLOSURE,
            info=True,
            reversibility=Reversibility.REVERSIBLE,
        ),
    )
    env = compute_safe_future_envelope(snap, closure, causal_rules=rules)
    fact = next(
        f for f in env.consequence_facts if f.consequence_kind == ConsequenceKind.PII_DISCLOSURE
    )
    assert fact.reversibility == Reversibility.IRREVERSIBLE


def test_p25_missing_rule_not_derived() -> None:
    snap, closure = _base_closure()
    env = compute_safe_future_envelope(snap, closure, causal_rules=())
    assert env.consequence_facts == ()


def test_p29_malformed_rule_rejected() -> None:
    with pytest.raises(InvalidCausalRule):
        CausalRule(
            rule_id="",
            tenant_id="t1",
            family=CausalRuleFamily.DIRECT_EFFECT,
            prerequisite_patterns=(("STATE_CHANGE", "x"),),
            output_kind=ConsequenceKind.STATE_CHANGE,
            output_subject_id="a",
            output_target_id="y",
            output_scope="s",
            reversibility=Reversibility.UNKNOWN,
            epistemic_status=EpistemicStatus.UNKNOWN,
        )


def test_p30_dense_graph_bounded() -> None:
    nodes = tuple(node(f"n{i}", NodeKind.TOOL) for i in range(20))
    edges = tuple(edge(f"e{i}", EdgeKind.CAN_CALL, f"n{i}", f"n{i + 1}") for i in range(19)) + (
        edge("e0", EdgeKind.CAN_CALL, "n0", "n1"),
    )
    snap = build_snapshot(nodes=nodes, edges=edges)
    closure = compute_capability_closure(snap, budget=CapabilityClosureBudget(max_iterations=10))
    env = compute_safe_future_envelope(
        snap,
        closure,
        causal_rules=(_bridge("call", "n1", ConsequenceKind.SERVICE_DISRUPTION),),
        budget=FutureEnvelopeBudget(max_consequences=50),
    )
    assert len(env.consequence_facts) <= 50
