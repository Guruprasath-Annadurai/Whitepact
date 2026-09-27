# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""Branch coverage for Gate 3 capability modules (repo OpenSSF gate)."""

from __future__ import annotations

import pytest
from tests.formula.helpers_gate3 import build_snapshot, edge, node

from responsibleai.formula.capability import CapabilityClosureBudget, compute_capability_closure
from responsibleai.formula.capability.actors import CapabilityActor
from responsibleai.formula.capability.budget import CapabilityClosureBudget as Budget
from responsibleai.formula.capability.closure import CapabilityClosureResult
from responsibleai.formula.capability.derivation import CapabilityDerivation
from responsibleai.formula.capability.facts import CapabilityFact
from responsibleai.formula.capability.joint import JointCapabilityRule, validate_joint_rules
from responsibleai.formula.capability.models import CapabilityKind
from responsibleai.formula.capability.provenance import validate_closure_provenance
from responsibleai.formula.capability.routes import merge_capability_routes, route_derivation_depth
from responsibleai.formula.capability.rules import RuleId
from responsibleai.formula.capability.support_aggregate import (
    aggregate_epistemic,
    aggregate_fact_from_witnesses,
    aggregate_is_direct,
    aggregate_support_kind,
)
from responsibleai.formula.epistemic import EpistemicStatus
from responsibleai.formula.errors import CapabilityTenantMismatch, InvalidCapability
from responsibleai.formula.graph.kinds import EdgeKind, NodeKind


def _witness(**kwargs) -> CapabilityDerivation:
    defaults = {
        "rule_id": RuleId.SEED,
        "output_semantic_key": ("t1", "t1", ("a",), "call", "t"),
        "prerequisite_keys": (),
        "prerequisite_witness_fingerprints": (),
        "graph_node_ids": ("a", "t"),
        "graph_edge_ids": (),
        "epistemic_status": EpistemicStatus.DECLARED,
        "derivation_depth": 1,
        "route_node_ids": ("a", "t"),
        "support_kind": CapabilityKind.DIRECT_TOOL,
        "support_is_direct": True,
    }
    defaults.update(kwargs)
    return CapabilityDerivation(**defaults)


def test_actor_validation_branches() -> None:
    with pytest.raises(InvalidCapability):
        CapabilityActor("t1", ())
    with pytest.raises(InvalidCapability):
        CapabilityActor("t1", ("a", "a"))
    with pytest.raises(InvalidCapability):
        CapabilityActor.coalition("t1", ())
    actor = CapabilityActor("t1", ("b", "a"))
    assert actor.member_ids == ("a", "b")
    with pytest.raises(CapabilityTenantMismatch):
        actor.assert_tenant("t2")


def test_budget_validate_all_fields() -> None:
    for field, msg in (
        ("max_iterations", "max_iterations"),
        ("max_facts", "max_facts"),
        ("max_derivations", "max_derivations"),
        ("max_rule_applications", "max_rule_applications"),
        ("max_path_depth", "max_path_depth"),
    ):
        kwargs = {field: 0}
        with pytest.raises(InvalidCapability, match=msg):
            Budget(**kwargs).validate()


def test_route_merge_branches() -> None:
    assert merge_capability_routes((), ("a", "b")) == ("a", "b")
    assert merge_capability_routes(("a",), ()) == ("a",)
    assert merge_capability_routes(("a", "b"), ("b", "c")) == ("a", "b", "c")
    assert merge_capability_routes(("a",), ("b",)) == ("a", "b")
    assert route_derivation_depth(("a",)) == 0
    assert route_derivation_depth(("a", "b")) == 1


def test_support_aggregate_branches() -> None:
    w1 = _witness(support_kind=CapabilityKind.COMPOSED, support_is_direct=False)
    w2 = _witness(support_kind=CapabilityKind.DIRECT_TOOL, support_is_direct=True)
    assert aggregate_support_kind((w1, w2)) == CapabilityKind.DIRECT_TOOL
    assert aggregate_is_direct((w1,)) is False
    assert aggregate_is_direct((w2,)) is True
    assert aggregate_epistemic(()) == EpistemicStatus.UNKNOWN
    base = CapabilityFact(
        tenant_id="t1",
        actor=CapabilityActor.single("t1", "a"),
        action="call",
        target_node_id="t",
        kind=CapabilityKind.COMPOSED,
        epistemic_status=EpistemicStatus.DECLARED,
        is_direct=False,
    )
    merged = aggregate_fact_from_witnesses(base, (w1, w2))
    assert merged.kind == CapabilityKind.DIRECT_TOOL
    assert merged.is_direct is True


def test_fact_actor_tenant_mismatch() -> None:
    with pytest.raises(ValueError, match="actor tenant"):
        CapabilityFact(
            tenant_id="t1",
            actor=CapabilityActor.single("t2", "a"),
            action="call",
            target_node_id="t",
            kind=CapabilityKind.DIRECT_TOOL,
            epistemic_status=EpistemicStatus.DECLARED,
            is_direct=True,
        )


def test_joint_validation_branches() -> None:
    snap = build_snapshot(
        nodes=(node("a", NodeKind.AGENT), node("db", NodeKind.DATABASE)),
        edges=(),
    )
    base_rule = JointCapabilityRule(
        rule_id="r1",
        tenant_id="t1",
        required_semantic_keys=(("t1", "t1", ("a",), "read", "db"),),
        coalition_member_ids=("a",),
        action="write",
        target_node_id="db",
    )
    validate_joint_rules(snap, (base_rule,))
    dup = JointCapabilityRule(
        rule_id="r1",
        tenant_id="t1",
        required_semantic_keys=(("t1", "t1", ("a",), "read", "db"),),
        coalition_member_ids=("a",),
        action="write",
        target_node_id="db",
    )
    validate_joint_rules(snap, (base_rule, dup))
    with pytest.raises(InvalidCapability):
        validate_joint_rules(
            snap,
            (
                base_rule,
                JointCapabilityRule(
                    rule_id="r1",
                    tenant_id="t1",
                    required_semantic_keys=(("t1", "t1", ("a",), "read", "db"),),
                    coalition_member_ids=("a",),
                    action="call",
                    target_node_id="db",
                ),
            ),
        )
    with pytest.raises(CapabilityTenantMismatch):
        validate_joint_rules(
            snap,
            (
                JointCapabilityRule(
                    rule_id="t2",
                    tenant_id="t2",
                    required_semantic_keys=(("t1", "t1", ("a",), "read", "db"),),
                    coalition_member_ids=("a",),
                    action="write",
                    target_node_id="db",
                ),
            ),
        )


def test_provenance_rule_branches() -> None:
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
    validate_closure_provenance(snap, result)


def test_state_budget_limits_on_add() -> None:
    snap = build_snapshot(
        nodes=(node("a", NodeKind.AGENT), node("t", NodeKind.TOOL)),
        edges=(edge("e1", EdgeKind.CAN_CALL, "a", "t"),),
    )
    result = compute_capability_closure(
        snap, budget=CapabilityClosureBudget(max_derivations=1, max_facts=10)
    )
    assert isinstance(result, CapabilityClosureResult)
