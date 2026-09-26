# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from tests.formula.helpers import make_grant

from responsibleai.formula.authority.algebra import (
    EffectiveAuthorityEvaluator,
    apply_explicit_denies,
    grant_intersection,
    grant_union,
)
from responsibleai.formula.authority.creation import (
    AuthorityCreationEvent,
    issuer_can_grant,
    validate_creation_event,
)
from responsibleai.formula.authority.lifecycle import consume_grant
from responsibleai.formula.authority.models import (
    AuthorityConstraint,
    AuthorityLifecycle,
    ExplicitDeny,
    OrgAuthorityCeilingModel,
)
from responsibleai.formula.authority.root import TenantRootPrincipal
from responsibleai.formula.authority.wildcard import WILDCARD
from responsibleai.formula.epistemic import EpistemicStatus
from responsibleai.formula.errors import ConsumedGrant, CrossTenantReference
from responsibleai.formula.serialization import (
    canonical_encode,
    canonical_sha256,
    serialize_authority_evaluation,
    serialize_grant,
    serialize_trace,
)
from responsibleai.formula.trace.trace import FormulaTrace, FormulaTraceEvent, TransitionClass
from responsibleai.formula.transitions import ProbabilityMass


def test_root_ceiling_blocks_broad_mint() -> None:
    ceiling = OrgAuthorityCeilingModel(
        tenant_id="t1", org_id="o1", allowed_actions=frozenset({"read"}), max_risk_class=3
    )
    root = TenantRootPrincipal("t1", "root-1", "org", "ev", "pol", ceiling=ceiling)
    grant = make_grant(
        "g",
        "agent",
        actions=frozenset({"write"}),
        risk=2,
        issuer_id="root-1",
    )
    grant = replace(grant, epistemic_status=EpistemicStatus.OBSERVED)
    assert not issuer_can_grant(
        "root-1",
        grant,
        (),
        EffectiveAuthorityEvaluator(ceiling=ceiling),
        grant.not_before,
        root=root,
    )


def test_constraint_one_shot_and_conditions_subset() -> None:
    parent = make_grant(
        "p",
        "org",
        allow_delegation=True,
        one_shot=True,
    )
    parent = replace(
        parent,
        constraints=AuthorityConstraint.build(
            allow_delegation=True,
            one_shot=True,
            conditions={"region": "eu"},
        ),
    )
    child = make_grant("c", "agent", delegator="org", one_shot=False)
    child = replace(
        child,
        constraints=AuthorityConstraint.build(allow_delegation=False, one_shot=False),
    )
    from responsibleai.formula.authority.algebra import authority_subset

    assert not authority_subset(child, parent)


def test_wildcard_intersection_and_deny_precedence() -> None:
    wild = make_grant("w", "s", actions=frozenset({WILDCARD}), resources=frozenset({"x"}))
    narrow = make_grant("n", "s", actions=frozenset({"read"}), resources=frozenset({"x"}))
    u_w = grant_union((wild,))
    u_n = grant_union((narrow,))
    inter = grant_intersection(u_w, u_n)
    assert any(t.action == "read" and t.resource == "x" for t in inter)

    tuples = grant_union((narrow,))
    broad_deny = ExplicitDeny(
        "d1", "t1", "s", frozenset({WILDCARD}), frozenset({WILDCARD}), specificity=1
    )
    narrow_deny = ExplicitDeny(
        "d2", "t1", "s", frozenset({"read"}), frozenset({"x"}), specificity=10
    )
    out = apply_explicit_denies(tuples, (broad_deny, narrow_deny), "s", "t1", narrow.not_before)
    assert out == frozenset()


def test_hard_proof_filters_declared_grants() -> None:
    g = make_grant("g", "s")
    ev = EffectiveAuthorityEvaluator()
    soft = ev.effective((g,), (), "s", "t1", g.not_before, hard_proof=False)
    hard = ev.effective((g,), (), "s", "t1", g.not_before, hard_proof=True)
    assert len(soft) > 0
    assert hard == frozenset()


def test_canonical_grant_trace_eval_roundtrip_stable() -> None:
    g = make_grant("g", "s")
    s1 = serialize_grant(g)
    s2 = serialize_grant(g)
    assert s1 == s2
    assert canonical_sha256(s1) == canonical_sha256(s2)

    ts = datetime(2026, 1, 1, tzinfo=UTC)
    ev = FormulaTraceEvent(
        "e1",
        "t1",
        "s",
        "read",
        "x",
        ts,
        1,
        "p1",
        ("g1",),
        ("ev",),
        TransitionClass.AUTHORITY_EVENT,
        "h0",
        "h1",
    )
    trace = FormulaTrace("t1", (ev,))
    assert serialize_trace(trace)["events"][0]["grant_refs"] == ["g1"]

    tuples = grant_union((g,))
    eval_blob = serialize_authority_evaluation(tuples, EffectiveAuthorityEvaluator(), "s", "t1")
    assert eval_blob["tenant_id"] == "t1"


def test_nested_set_canonicalization() -> None:
    a = canonical_encode({1, 2, 3})
    b = canonical_encode({3, 2, 1})
    assert a == b


def test_creation_event_tenant_mismatch() -> None:
    g = make_grant("g", "s", tenant="t1")
    event = AuthorityCreationEvent(
        tenant_id="t2",
        issuer_id=g.issuer_id,
        subject_id=g.subject.subject_id,
        new_grant=g,
        reason="x",
        at=g.not_before,
        evidence_ref="ev",
        policy_version="pol",
    )
    with pytest.raises(CrossTenantReference):
        validate_creation_event(event)


def test_consume_requires_active_lifecycle() -> None:
    pending = make_grant("p", "s", lifecycle=AuthorityLifecycle.PENDING)
    with pytest.raises(ConsumedGrant):
        consume_grant(pending, pending.not_before)


def test_empty_probability_mass_rejected() -> None:
    with pytest.raises(ValueError, match="empty probability mass"):
        ProbabilityMass(())


def test_immutable_constraint_conditions_snapshot() -> None:
    c = AuthorityConstraint.build(conditions={"k": "v"})
    snap = dict(c.conditions)
    snap["k"] = "mutated"
    assert c.conditions["k"] == "v"
