# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""Gate 3 correction pass — depth, witnesses, epistemic, coalition, budgets."""

from __future__ import annotations

import itertools

import pytest
from dataclasses import replace
from tests.formula.helpers_gate3 import build_snapshot, edge, node

from responsibleai.formula.capability import (
    CapabilityClosureBudget,
    ClosureStatus,
    compute_capability_closure,
    serialize_closure_result,
)
from responsibleai.formula.capability.actors import CapabilityActor
from responsibleai.formula.capability.facts import CapabilityFact
from responsibleai.formula.capability.joint import JointCapabilityRule
from responsibleai.formula.capability.models import CapabilityKind
from responsibleai.formula.capability.provenance import validate_closure_provenance
from responsibleai.formula.capability.rules import RuleId
from responsibleai.formula.epistemic import EpistemicStatus
from responsibleai.formula.errors import InvalidCapability
from responsibleai.formula.graph.kinds import EdgeKind, NodeKind
from responsibleai.formula.invariants import FormulaInvariantChecker
from responsibleai.formula.serialization import canonical_sha256


def _deep_chain_snapshot():
    return build_snapshot(
        nodes=(
            node("a", NodeKind.AGENT),
            node("m1", NodeKind.MCP_SERVER),
            node("m2", NodeKind.MCP_SERVER),
            node("api", NodeKind.API),
            node("tool", NodeKind.TOOL),
            node("db", NodeKind.DATABASE),
        ),
        edges=(
            edge("e1", EdgeKind.CAN_CALL, "a", "m1"),
            edge("e2", EdgeKind.CAN_CALL, "m1", "m2"),
            edge("e3", EdgeKind.CAN_CALL, "m2", "api"),
            edge("e4", EdgeKind.CAN_CALL, "api", "tool"),
            edge("e5", EdgeKind.CAN_WRITE, "tool", "db"),
        ),
    )


def test_cumulative_depth_deep_chain() -> None:
    snap = _deep_chain_snapshot()
    result = compute_capability_closure(snap, budget=CapabilityClosureBudget(max_iterations=32))
    write_witnesses = [
        d
        for d in result.derivations
        if d.output_semantic_key[3] == "write" and d.output_semantic_key[4] == "db"
    ]
    assert write_witnesses
    assert max(d.derivation_depth for d in write_witnesses) >= 5


def test_max_path_depth_insufficient_is_incomplete() -> None:
    snap = _deep_chain_snapshot()
    shallow = compute_capability_closure(
        snap, budget=CapabilityClosureBudget(max_path_depth=3, max_iterations=32)
    )
    assert shallow.status == ClosureStatus.INCOMPLETE
    assert any("max_path_depth" in n for n in shallow.unresolved_notes)


def test_alternate_witnesses_two_tools() -> None:
    snap = build_snapshot(
        nodes=(
            node("a", NodeKind.AGENT),
            node("t1", NodeKind.TOOL),
            node("t2", NodeKind.TOOL),
            node("db", NodeKind.DATABASE),
        ),
        edges=(
            edge("e1", EdgeKind.CAN_CALL, "a", "t1"),
            edge("e2", EdgeKind.CAN_CALL, "a", "t2"),
            edge("e3", EdgeKind.CAN_WRITE, "t1", "db"),
            edge("e4", EdgeKind.CAN_WRITE, "t2", "db"),
        ),
    )
    result = compute_capability_closure(snap)
    write_key = next(f.semantic_key() for f in result.facts if f.action == "write")
    witnesses = [d for d in result.derivations if d.output_semantic_key == write_key]
    assert len(witnesses) >= 2


def test_direct_extraction_provenance() -> None:
    snap = build_snapshot(
        nodes=(node("a", NodeKind.AGENT), node("t", NodeKind.TOOL)),
        edges=(edge("e1", EdgeKind.CAN_CALL, "a", "t"),),
    )
    result = compute_capability_closure(snap)
    direct = [d for d in result.derivations if d.rule_id == RuleId.DIRECT_EXTRACTION]
    assert len(direct) == 1
    assert direct[0].graph_edge_ids == ("e1",)


def test_duplicate_seed_order_independent() -> None:
    snap = build_snapshot(nodes=(node("a", NodeKind.AGENT), node("t", NodeKind.TOOL)))
    base = CapabilityFact(
        tenant_id="t1",
        actor=CapabilityActor.single("t1", "a"),
        action="call",
        target_node_id="t",
        kind=CapabilityKind.DIRECT_TOOL,
        epistemic_status=EpistemicStatus.VERIFIED,
        is_direct=True,
    )
    dup = replace(base, epistemic_status=EpistemicStatus.UNKNOWN, is_direct=False)
    r1 = compute_capability_closure(snap, seeds=(base, dup))
    r2 = compute_capability_closure(snap, seeds=(dup, base))
    assert canonical_sha256(serialize_closure_result(r1)) == canonical_sha256(
        serialize_closure_result(r2)
    )
    fact = next(f for f in r1.facts if f.target_node_id == "t")
    assert fact.epistemic_status == EpistemicStatus.UNKNOWN


def test_epistemic_unknown_target_on_direct() -> None:
    snap = build_snapshot(
        nodes=(
            replace(node("a", NodeKind.AGENT), epistemic_status=EpistemicStatus.VERIFIED),
            replace(node("t", NodeKind.TOOL), epistemic_status=EpistemicStatus.UNKNOWN),
        ),
        edges=(
            replace(
                edge("e1", EdgeKind.CAN_CALL, "a", "t"),
                epistemic_status=EpistemicStatus.VERIFIED,
            ),
        ),
    )
    result = compute_capability_closure(snap)
    f = next(x for x in result.facts if x.target_node_id == "t")
    assert f.epistemic_status == EpistemicStatus.UNKNOWN


def test_invalid_budget_rejected() -> None:
    with pytest.raises(InvalidCapability):
        compute_capability_closure(
            build_snapshot(nodes=(node("a", NodeKind.AGENT),)),
            budget=CapabilityClosureBudget(max_iterations=0),
        )


def test_coalition_actor_canonical() -> None:
    c1 = CapabilityActor.coalition("t1", ("b", "a"))
    c2 = CapabilityActor.coalition("t1", ("a", "b"))
    assert c1.member_ids == c2.member_ids == ("a", "b")


def test_joint_capability_explicit_rule() -> None:
    snap = build_snapshot(
        nodes=(
            node("a", NodeKind.AGENT),
            node("b", NodeKind.AGENT),
            node("lock", NodeKind.TOOL),
            node("db", NodeKind.DATABASE),
        ),
        edges=(
            edge("e1", EdgeKind.CAN_READ, "a", "lock"),
            edge("e2", EdgeKind.CAN_WRITE, "b", "db"),
        ),
    )
    base = compute_capability_closure(snap)
    pa = next(f.semantic_key() for f in base.facts if f.actor.member_ids == ("a",))
    pb = next(
        f.semantic_key()
        for f in base.facts
        if f.actor.member_ids == ("b",) and f.action == "write"
    )
    joint = (
        JointCapabilityRule(
            rule_id="j1",
            tenant_id="t1",
            required_semantic_keys=(pa, pb),
            coalition_member_ids=("a", "b"),
            action="write",
            target_node_id="db",
        ),
    )
    result = compute_capability_closure(snap, joint_rules=joint)
    coalition_facts = [
        f for f in result.facts if f.actor.member_ids == ("a", "b") and f.action == "write"
    ]
    assert coalition_facts
    r_no_joint = compute_capability_closure(snap)
    assert not [
        f
        for f in r_no_joint.facts
        if len(f.actor.member_ids) == 2 and f.action == "write"
    ]
    snap_no_a = build_snapshot(
        nodes=(
            node("b", NodeKind.AGENT),
            node("lock", NodeKind.TOOL),
            node("db", NodeKind.DATABASE),
        ),
        edges=(edge("e2", EdgeKind.CAN_WRITE, "b", "db"),),
    )
    base_no_a = compute_capability_closure(snap_no_a)
    pb_only = next(
        f.semantic_key()
        for f in base_no_a.facts
        if f.actor.member_ids == ("b",) and f.action == "write"
    )
    r_missing_a = compute_capability_closure(
        snap_no_a,
        joint_rules=(
            JointCapabilityRule(
                rule_id="j2",
                tenant_id="t1",
                required_semantic_keys=(pa, pb_only),
                coalition_member_ids=("a", "b"),
                action="write",
                target_node_id="db",
            ),
        ),
    )
    assert not [
        f for f in r_missing_a.facts if len(f.actor.member_ids) == 2 and f.action == "write"
    ]


def test_provenance_dag_valid() -> None:
    snap = _deep_chain_snapshot()
    result = compute_capability_closure(snap, budget=CapabilityClosureBudget(max_iterations=32))
    validate_closure_provenance(snap, result)


def test_property_matrix_smoke() -> None:
    snap = build_snapshot(
        nodes=(node("a", NodeKind.AGENT), node("t", NodeKind.TOOL), node("db", NodeKind.DATABASE)),
        edges=(
            edge("e1", EdgeKind.CAN_CALL, "a", "t"),
            edge("e2", EdgeKind.CAN_WRITE, "t", "db"),
        ),
    )
    result = compute_capability_closure(snap)
    checker = FormulaInvariantChecker()
    assert not checker.check_capability_tenant_isolation(result)
    assert not checker.check_capability_provenance(result)
    assert not checker.check_capability_budget_status(result)
    assert not checker.check_capability_closure_idempotent(snap, result)


def test_graph_insertion_order_hash_stable() -> None:
    snap_a = build_snapshot(
        nodes=(node("a", NodeKind.AGENT), node("t", NodeKind.TOOL)),
        edges=(edge("e1", EdgeKind.CAN_CALL, "a", "t"),),
    )
    snap_b = build_snapshot(
        nodes=(node("t", NodeKind.TOOL), node("a", NodeKind.AGENT)),
        edges=(edge("e1", EdgeKind.CAN_CALL, "a", "t"),),
    )
    h1 = canonical_sha256(serialize_closure_result(compute_capability_closure(snap_a)))
    h2 = canonical_sha256(serialize_closure_result(compute_capability_closure(snap_b)))
    assert h1 == h2


def test_seed_permutations_stable() -> None:
    snap = build_snapshot(nodes=(node("a", NodeKind.AGENT), node("t", NodeKind.TOOL)))
    seeds = tuple(
        CapabilityFact(
            tenant_id="t1",
            actor=CapabilityActor.single("t1", "a"),
            action="call",
            target_node_id="t",
            kind=CapabilityKind.DIRECT_TOOL,
            epistemic_status=status,
            is_direct=direct,
        )
        for status, direct in (
            (EpistemicStatus.VERIFIED, True),
            (EpistemicStatus.UNKNOWN, False),
        )
    )
    hashes = []
    for perm in itertools.permutations(seeds):
        r = compute_capability_closure(snap, seeds=perm)
        hashes.append(canonical_sha256(serialize_closure_result(r)))
    assert len(set(hashes)) == 1
