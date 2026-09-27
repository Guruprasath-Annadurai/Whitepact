# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""Gate 3 — capability closure engine tests."""

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
from responsibleai.formula.capability.models import CapabilityKind
from responsibleai.formula.epistemic import EpistemicStatus
from responsibleai.formula.errors import CapabilityTenantMismatch
from responsibleai.formula.graph.kinds import EdgeKind, NodeKind
from responsibleai.formula.invariants import FormulaInvariantChecker
from responsibleai.formula.serialization import canonical_sha256


def _has_capability(result, actor: str, action: str, target: str) -> bool:
    return any(
        f.actor.member_ids == (actor,) and f.action == action and f.target_node_id == target
        for f in result.facts
    )


def test_direct_agent_can_call_tool() -> None:
    snap = build_snapshot(
        nodes=(node("a", NodeKind.AGENT), node("t", NodeKind.TOOL)),
        edges=(edge("e1", EdgeKind.CAN_CALL, "a", "t"),),
    )
    result = compute_capability_closure(snap)
    assert _has_capability(result, "a", "call", "t")
    assert result.status == ClosureStatus.COMPLETE
    assert any(f.is_direct for f in result.facts)


def test_tool_composition_write() -> None:
    snap = build_snapshot(
        nodes=(
            node("a", NodeKind.AGENT),
            node("tool", NodeKind.TOOL),
            node("db", NodeKind.DATABASE),
        ),
        edges=(
            edge("e1", EdgeKind.CAN_CALL, "a", "tool"),
            edge("e2", EdgeKind.CAN_WRITE, "tool", "db"),
        ),
    )
    result = compute_capability_closure(snap)
    assert _has_capability(result, "a", "write", "db")
    composed = [
        f for f in result.facts if f.target_node_id == "db" and f.actor.member_ids == ("a",)
    ]
    assert composed and not composed[0].is_direct
    assert composed[0].kind == CapabilityKind.COMPOSED


def test_mcp_api_chain() -> None:
    snap = build_snapshot(
        nodes=(
            node("a", NodeKind.AGENT),
            node("m", NodeKind.MCP_SERVER),
            node("api", NodeKind.API),
            node("r", NodeKind.DATABASE),
        ),
        edges=(
            edge("e1", EdgeKind.CAN_CALL, "a", "m"),
            edge("e2", EdgeKind.CAN_CALL, "m", "api"),
            edge("e3", EdgeKind.CAN_WRITE, "api", "r"),
        ),
    )
    result = compute_capability_closure(snap, budget=CapabilityClosureBudget(max_iterations=8))
    assert _has_capability(result, "a", "write", "r")


def test_capability_without_authority() -> None:
    snap = build_snapshot(
        nodes=(node("a", NodeKind.AGENT), node("t", NodeKind.TOOL)),
        edges=(edge("e1", EdgeKind.CAN_CALL, "a", "t"),),
    )
    result = compute_capability_closure(snap)
    assert result.facts
    checker = FormulaInvariantChecker()
    assert not checker.check_capability_not_authority(True, False, False)


def test_has_authority_does_not_create_capability() -> None:
    snap = build_snapshot(
        nodes=(node("a", NodeKind.AGENT), node("g", NodeKind.EXECUTION_GRANT)),
        edges=(edge("e1", EdgeKind.HAS_AUTHORITY, "a", "g"),),
    )
    result = compute_capability_closure(snap)
    assert result.facts == ()


def test_credential_unlock_explicit() -> None:
    snap = build_snapshot(
        nodes=(
            node("a", NodeKind.AGENT),
            node("cred", NodeKind.CREDENTIAL),
            node("api", NodeKind.API),
        ),
        edges=(
            edge("e1", EdgeKind.CAN_READ, "a", "cred"),
            edge("e2", EdgeKind.REQUIRES, "cred", "api", grants="call"),
        ),
    )
    result = compute_capability_closure(snap)
    assert _has_capability(result, "a", "call", "api")


def test_credential_missing_prerequisite() -> None:
    snap = build_snapshot(
        nodes=(
            node("a", NodeKind.AGENT),
            node("cred", NodeKind.CREDENTIAL),
            node("api", NodeKind.API),
        ),
        edges=(edge("e2", EdgeKind.REQUIRES, "cred", "api", grants="call"),),
    )
    result = compute_capability_closure(snap)
    assert not _has_capability(result, "a", "call", "api")


def test_information_reveals_chain() -> None:
    snap = build_snapshot(
        nodes=(
            node("a", NodeKind.AGENT),
            node("file", NodeKind.FILESYSTEM),
            node("cfg", NodeKind.DATASET),
        ),
        edges=(
            edge("e1", EdgeKind.CAN_READ, "a", "file"),
            edge("e2", EdgeKind.REVEALS, "file", "cfg"),
        ),
    )
    result = compute_capability_closure(snap)
    assert _has_capability(result, "a", "read", "cfg")


def test_fake_name_no_implicit_unlock() -> None:
    snap = build_snapshot(
        nodes=(
            node("a", NodeKind.AGENT),
            node("prod_api_key", NodeKind.SECRET),
            node("api", NodeKind.API),
        ),
        edges=(edge("e1", EdgeKind.CAN_READ, "a", "prod_api_key"),),
    )
    result = compute_capability_closure(snap)
    assert not _has_capability(result, "a", "call", "api")


def test_cross_tenant_seed_rejected() -> None:
    snap = build_snapshot(nodes=(node("a", NodeKind.AGENT),))
    bad = CapabilityFact(
        tenant_id="t2",
        actor=CapabilityActor.single("t2", "a"),
        action="call",
        target_node_id="x",
        kind=CapabilityKind.DIRECT_TOOL,
        epistemic_status=EpistemicStatus.DECLARED,
        is_direct=True,
    )
    with pytest.raises(CapabilityTenantMismatch):
        compute_capability_closure(snap, seeds=(bad,))


def test_cycle_terminates() -> None:
    snap = build_snapshot(
        nodes=(node("a", NodeKind.AGENT), node("b", NodeKind.AGENT)),
        edges=(
            edge("e1", EdgeKind.CAN_CALL, "a", "b"),
            edge("e2", EdgeKind.CAN_CALL, "b", "a"),
        ),
    )
    result = compute_capability_closure(snap, budget=CapabilityClosureBudget(max_iterations=20))
    assert result.status in (ClosureStatus.COMPLETE, ClosureStatus.INCOMPLETE)


def test_budget_exhaustion_incomplete() -> None:
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
            edge("e4", EdgeKind.CAN_WRITE, "t1", "db"),
        ),
    )
    result = compute_capability_closure(
        snap,
        budget=CapabilityClosureBudget(max_iterations=50, max_facts=3, max_rule_applications=50),
    )
    assert result.status == ClosureStatus.INCOMPLETE
    checker = FormulaInvariantChecker()
    assert not checker.check_capability_budget_status(result)


def test_deterministic_hash() -> None:
    snap = build_snapshot(
        nodes=(node("a", NodeKind.AGENT), node("t", NodeKind.TOOL), node("db", NodeKind.DATABASE)),
        edges=(
            edge("e1", EdgeKind.CAN_CALL, "a", "t"),
            edge("e2", EdgeKind.CAN_WRITE, "t", "db"),
        ),
    )
    r1 = serialize_closure_result(compute_capability_closure(snap))
    r2 = serialize_closure_result(compute_capability_closure(snap))
    assert canonical_sha256(r1) == canonical_sha256(r2)


def test_multi_agent_relay() -> None:
    snap = build_snapshot(
        nodes=(node("a", NodeKind.AGENT), node("b", NodeKind.AGENT), node("db", NodeKind.DATABASE)),
        edges=(
            edge("e1", EdgeKind.CAN_CALL, "a", "b"),
            edge("e2", EdgeKind.CAN_WRITE, "b", "db"),
        ),
    )
    result = compute_capability_closure(snap)
    assert _has_capability(result, "a", "write", "db")


def test_coexisting_agents_no_emergent_capability() -> None:
    snap = build_snapshot(
        nodes=(node("a", NodeKind.AGENT), node("b", NodeKind.AGENT), node("db", NodeKind.DATABASE)),
        edges=(edge("e2", EdgeKind.CAN_WRITE, "b", "db"),),
    )
    result = compute_capability_closure(snap)
    assert not _has_capability(result, "a", "write", "db")


def test_epistemic_weakest_link() -> None:
    from responsibleai.formula.capability.epistemic_compose import compose_epistemic

    assert (
        compose_epistemic(EpistemicStatus.VERIFIED, EpistemicStatus.UNKNOWN)
        == EpistemicStatus.UNKNOWN
    )
