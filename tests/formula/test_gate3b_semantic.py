# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""Gate 3B — witness-aware composition, joint validation, property matrix."""

from __future__ import annotations

import pytest
from tests.formula.helpers_gate3 import build_snapshot, edge, node

from responsibleai.formula.capability import (
    CapabilityClosureBudget,
    ClosureStatus,
    compute_capability_closure,
    serialize_closure_result,
)
from responsibleai.formula.capability.actors import CapabilityActor
from responsibleai.formula.capability.facts import CapabilityFact
from responsibleai.formula.capability.joint import JointCapabilityRule, validate_joint_rules
from responsibleai.formula.capability.models import CapabilityKind
from responsibleai.formula.capability.provenance import validate_closure_provenance
from responsibleai.formula.epistemic import EpistemicStatus
from responsibleai.formula.errors import CapabilityTenantMismatch, InvalidCapability
from responsibleai.formula.graph.kinds import EdgeKind, NodeKind
from responsibleai.formula.invariants import FormulaInvariantChecker
from responsibleai.formula.serialization import canonical_sha256


def _has(result, actor: str, action: str, target: str) -> bool:
    return any(
        f.actor.member_ids == (actor,) and f.action == action and f.target_node_id == target
        for f in result.facts
    )


def test_support_aware_short_route_composes_when_long_blocked() -> None:
    snap = build_snapshot(
        nodes=(
            node("a", NodeKind.AGENT),
            node("m1", NodeKind.MCP_SERVER),
            node("m2", NodeKind.MCP_SERVER),
            node("t", NodeKind.TOOL),
            node("db", NodeKind.DATABASE),
        ),
        edges=(
            edge("e0", EdgeKind.CAN_CALL, "a", "t"),
            edge("e1", EdgeKind.CAN_CALL, "a", "m1"),
            edge("e2", EdgeKind.CAN_CALL, "m1", "m2"),
            edge("e3", EdgeKind.CAN_CALL, "m2", "t"),
            edge("e4", EdgeKind.CAN_WRITE, "t", "db"),
        ),
    )
    result = compute_capability_closure(
        snap,
        budget=CapabilityClosureBudget(max_path_depth=3, max_iterations=24),
    )
    assert _has(result, "a", "write", "db")


def test_credential_unlock_all_actors() -> None:
    snap_a = build_snapshot(
        nodes=(
            node("a", NodeKind.AGENT),
            node("b", NodeKind.AGENT),
            node("cred", NodeKind.CREDENTIAL),
            node("api", NodeKind.API),
        ),
        edges=(
            edge("e1", EdgeKind.CAN_READ, "a", "cred"),
            edge("e2", EdgeKind.CAN_READ, "b", "cred"),
            edge("e3", EdgeKind.REQUIRES, "cred", "api", grants="call"),
        ),
    )
    snap_b = build_snapshot(
        nodes=(
            node("b", NodeKind.AGENT),
            node("a", NodeKind.AGENT),
            node("cred", NodeKind.CREDENTIAL),
            node("api", NodeKind.API),
        ),
        edges=(
            edge("e2", EdgeKind.CAN_READ, "b", "cred"),
            edge("e1", EdgeKind.CAN_READ, "a", "cred"),
            edge("e3", EdgeKind.REQUIRES, "cred", "api", grants="call"),
        ),
    )
    r1 = compute_capability_closure(snap_a)
    r2 = compute_capability_closure(snap_b)
    assert _has(r1, "a", "call", "api")
    assert _has(r1, "b", "call", "api")
    assert canonical_sha256(serialize_closure_result(r1)) == canonical_sha256(
        serialize_closure_result(r2)
    )


def test_kind_support_permutation_independent() -> None:
    snap = build_snapshot(nodes=(node("a", NodeKind.AGENT), node("t", NodeKind.TOOL)))
    direct = CapabilityFact(
        tenant_id="t1",
        actor=CapabilityActor.single("t1", "a"),
        action="call",
        target_node_id="t",
        kind=CapabilityKind.DIRECT_TOOL,
        epistemic_status=EpistemicStatus.VERIFIED,
        is_direct=True,
    )
    composed = CapabilityFact(
        tenant_id="t1",
        actor=CapabilityActor.single("t1", "a"),
        action="call",
        target_node_id="t",
        kind=CapabilityKind.COMPOSED,
        epistemic_status=EpistemicStatus.VERIFIED,
        is_direct=False,
    )
    r1 = compute_capability_closure(snap, seeds=(direct, composed))
    r2 = compute_capability_closure(snap, seeds=(composed, direct))
    assert canonical_sha256(serialize_closure_result(r1)) == canonical_sha256(
        serialize_closure_result(r2)
    )
    fact = next(f for f in r1.facts if f.target_node_id == "t")
    assert fact.kind == CapabilityKind.DIRECT_TOOL
    assert fact.is_direct is True


def test_reveals_cycle_acyclic_provenance() -> None:
    snap = build_snapshot(
        nodes=(
            node("a", NodeKind.AGENT),
            node("x", NodeKind.DATASET),
            node("y", NodeKind.DATASET),
        ),
        edges=(
            edge("e1", EdgeKind.CAN_READ, "a", "x"),
            edge("e2", EdgeKind.REVEALS, "x", "y"),
            edge("e3", EdgeKind.REVEALS, "y", "x"),
        ),
    )
    result = compute_capability_closure(snap)
    validate_closure_provenance(snap, result)
    assert _has(result, "a", "read", "x")
    assert _has(result, "a", "read", "y")


def test_joint_empty_prerequisites_rejected() -> None:
    snap = build_snapshot(nodes=(node("a", NodeKind.AGENT),))
    bad = JointCapabilityRule(
        rule_id="empty",
        tenant_id="t1",
        required_semantic_keys=(),
        coalition_member_ids=("a",),
        action="write",
        target_node_id="a",
    )
    with pytest.raises(InvalidCapability):
        validate_joint_rules(snap, (bad,))
    with pytest.raises(InvalidCapability):
        compute_capability_closure(snap, joint_rules=(bad,))


def test_joint_ghost_member_rejected() -> None:
    snap = build_snapshot(nodes=(node("b", NodeKind.AGENT), node("db", NodeKind.DATABASE)))
    rule = JointCapabilityRule(
        rule_id="g",
        tenant_id="t1",
        required_semantic_keys=(("t1", "t1", ("b",), "write", "db"),),
        coalition_member_ids=("ghost", "b"),
        action="write",
        target_node_id="db",
    )
    with pytest.raises(InvalidCapability):
        validate_joint_rules(snap, (rule,))


def test_property_p1_seed_inclusion() -> None:
    snap = build_snapshot(
        nodes=(node("a", NodeKind.AGENT), node("t", NodeKind.TOOL)),
        edges=(edge("e1", EdgeKind.CAN_CALL, "a", "t"),),
    )
    seed = next(iter(compute_capability_closure(snap).facts))
    out = compute_capability_closure(snap, seeds=(seed,))
    assert seed.semantic_key() in {f.semantic_key() for f in out.facts}


def test_property_p2_idempotence() -> None:
    snap = build_snapshot(
        nodes=(node("a", NodeKind.AGENT), node("t", NodeKind.TOOL), node("db", NodeKind.DATABASE)),
        edges=(
            edge("e1", EdgeKind.CAN_CALL, "a", "t"),
            edge("e2", EdgeKind.CAN_WRITE, "t", "db"),
        ),
    )
    once = compute_capability_closure(snap)
    checker = FormulaInvariantChecker()
    assert not checker.check_capability_closure_idempotent(snap, once)


def test_property_p12_budget_incomplete() -> None:
    snap = build_snapshot(
        nodes=(
            node("a", NodeKind.AGENT),
            node("t1", NodeKind.TOOL),
            node("t2", NodeKind.TOOL),
            node("db", NodeKind.DATABASE),
        ),
        edges=(
            edge("e1", EdgeKind.CAN_CALL, "a", "t1"),
            edge("e2", EdgeKind.CAN_CALL, "t1", "t2"),
            edge("e3", EdgeKind.CAN_WRITE, "t2", "db"),
        ),
    )
    result = compute_capability_closure(
        snap, budget=CapabilityClosureBudget(max_iterations=1, max_rule_applications=50)
    )
    assert result.status == ClosureStatus.INCOMPLETE


def test_property_p3_monotone() -> None:
    snap = build_snapshot(
        nodes=(node("a", NodeKind.AGENT), node("t", NodeKind.TOOL)),
        edges=(edge("e1", EdgeKind.CAN_CALL, "a", "t"),),
    )
    empty = compute_capability_closure(snap, seeds=())
    with_seed = compute_capability_closure(snap, seeds=empty.facts)
    checker = FormulaInvariantChecker()
    assert not checker.check_capability_closure_monotone(snap, (), empty.facts)


def test_property_p4_determinism() -> None:
    snap = build_snapshot(
        nodes=(node("a", NodeKind.AGENT), node("t", NodeKind.TOOL)),
        edges=(edge("e1", EdgeKind.CAN_CALL, "a", "t"),),
    )
    h1 = canonical_sha256(serialize_closure_result(compute_capability_closure(snap)))
    h2 = canonical_sha256(serialize_closure_result(compute_capability_closure(snap)))
    assert h1 == h2


def test_property_p7_tenant_isolation() -> None:
    snap = build_snapshot(nodes=(node("a", NodeKind.AGENT), node("t", NodeKind.TOOL)))
    bad = CapabilityFact(
        tenant_id="t2",
        actor=CapabilityActor.single("t2", "a"),
        action="call",
        target_node_id="t",
        kind=CapabilityKind.DIRECT_TOOL,
        epistemic_status=EpistemicStatus.DECLARED,
        is_direct=True,
    )
    with pytest.raises(CapabilityTenantMismatch):
        compute_capability_closure(snap, seeds=(bad,))


def test_property_p9_p10_capability_not_authority() -> None:
    snap_cap = build_snapshot(
        nodes=(node("a", NodeKind.AGENT), node("t", NodeKind.TOOL)),
        edges=(edge("e1", EdgeKind.CAN_CALL, "a", "t"),),
    )
    assert compute_capability_closure(snap_cap).facts
    snap_auth = build_snapshot(
        nodes=(node("a", NodeKind.AGENT), node("g", NodeKind.EXECUTION_GRANT)),
        edges=(edge("e1", EdgeKind.HAS_AUTHORITY, "a", "g"),),
    )
    assert compute_capability_closure(snap_auth).facts == ()


def test_property_p13_cycle_terminates() -> None:
    snap = build_snapshot(
        nodes=(node("a", NodeKind.AGENT), node("b", NodeKind.AGENT)),
        edges=(
            edge("e1", EdgeKind.CAN_CALL, "a", "b"),
            edge("e2", EdgeKind.CAN_CALL, "b", "a"),
        ),
    )
    result = compute_capability_closure(snap)
    checker = FormulaInvariantChecker()
    assert not checker.check_capability_cycle_terminates(result)


def test_property_p16_distinct_support_kinds() -> None:
    snap = build_snapshot(
        nodes=(node("a", NodeKind.AGENT), node("t", NodeKind.TOOL)),
        edges=(edge("e1", EdgeKind.CAN_CALL, "a", "t"),),
    )
    result = compute_capability_closure(snap)
    kinds = {d.support_kind for d in result.derivations}
    assert CapabilityKind.DIRECT_TOOL in kinds
