# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""Branch coverage for Gate 4 future envelope modules."""

from __future__ import annotations

from dataclasses import replace

import pytest
from tests.formula.helpers_gate3 import build_snapshot, edge, node

from responsibleai.formula.capability import compute_capability_closure
from responsibleai.formula.epistemic import EpistemicStatus
from responsibleai.formula.errors import CausalTenantMismatch, InvalidCausalRule
from responsibleai.formula.future.engine import compute_safe_future_envelope
from responsibleai.formula.future.facts import ConsequenceFact
from responsibleai.formula.future.models import (
    CausalRuleFamily,
    ConsequenceKind,
    ConsequenceReachability,
    Reversibility,
)
from responsibleai.formula.future.rules import CausalRule, validate_causal_rules
from responsibleai.formula.future.serialize import compute_envelope_hash, serialize_envelope
from responsibleai.formula.graph.kinds import EdgeKind, NodeKind


def test_fact_validation_branches() -> None:
    with pytest.raises(ValueError):
        ConsequenceFact(
            tenant_id="",
            subject_id="a",
            target_id="t",
            consequence_kind=ConsequenceKind.STATE_CHANGE,
            scope="s",
            reversibility=Reversibility.UNKNOWN,
            persistence=False,
            information_sensitive=False,
            epistemic_status=EpistemicStatus.UNKNOWN,
            reachability=ConsequenceReachability.SUPPORTED,
        )


def test_causal_rule_bridge_and_edge_validation() -> None:
    with pytest.raises(InvalidCausalRule):
        CausalRule(
            rule_id="x",
            tenant_id="t1",
            family=CausalRuleFamily.CAPABILITY_BRIDGE,
            prerequisite_patterns=(),
            output_kind=ConsequenceKind.STATE_CHANGE,
            output_subject_id="a",
            output_target_id="t",
            output_scope="s",
            reversibility=Reversibility.UNKNOWN,
            epistemic_status=EpistemicStatus.UNKNOWN,
        )
    with pytest.raises(InvalidCausalRule):
        CausalRule(
            rule_id="y",
            tenant_id="t1",
            family=CausalRuleFamily.PROPAGATED_EFFECT,
            prerequisite_patterns=(("STATE_CHANGE", "t"),),
            output_kind=ConsequenceKind.STATE_CHANGE,
            output_subject_id="a",
            output_target_id="t",
            output_scope="s",
            reversibility=Reversibility.UNKNOWN,
            epistemic_status=EpistemicStatus.UNKNOWN,
        )


def test_validate_causal_rules_unknown_edge() -> None:
    snap = build_snapshot(nodes=(node("a", NodeKind.AGENT),), edges=())
    rule = CausalRule(
        rule_id="r",
        tenant_id="t1",
        family=CausalRuleFamily.PROPAGATED_EFFECT,
        prerequisite_patterns=(("STATE_CHANGE", "a"),),
        output_kind=ConsequenceKind.STATE_CHANGE,
        output_subject_id="a",
        output_target_id="a",
        output_scope="s",
        reversibility=Reversibility.UNKNOWN,
        epistemic_status=EpistemicStatus.UNKNOWN,
        graph_edge_id="missing",
    )
    with pytest.raises(InvalidCausalRule):
        validate_causal_rules(snap, (rule,))


def test_engine_closure_hash_mismatch() -> None:
    snap = build_snapshot(
        nodes=(node("a", NodeKind.AGENT), node("t", NodeKind.TOOL)),
        edges=(edge("e1", EdgeKind.CAN_READ, "a", "t"),),
    )
    closure = compute_capability_closure(snap)
    bad_closure = replace(closure, graph_content_hash="deadbeef")
    with pytest.raises(CausalTenantMismatch):
        compute_safe_future_envelope(snap, bad_closure, causal_rules=())


def test_engine_invalid_horizon() -> None:
    snap = build_snapshot(nodes=(node("a", NodeKind.AGENT),), edges=())
    closure = compute_capability_closure(snap)
    with pytest.raises(ValueError):
        compute_safe_future_envelope(snap, closure, horizon=0)


def test_serialize_and_hash_nonempty() -> None:
    snap = build_snapshot(
        nodes=(node("a", NodeKind.AGENT), node("t", NodeKind.TOOL)),
        edges=(edge("e1", EdgeKind.CAN_READ, "a", "t"),),
    )
    closure = compute_capability_closure(snap)
    rule = CausalRule(
        rule_id="b",
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
    env = compute_safe_future_envelope(snap, closure, causal_rules=(rule,))
    assert env.canonical_hash == compute_envelope_hash(env)
    assert serialize_envelope(env)["tenant_id"] == "t1"
