# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from tests.formula.helpers import make_grant

from responsibleai.formula.authority.algebra import (
    EffectiveAuthorityEvaluator,
    apply_explicit_denies,
    grant_contained_in_issuer_authority,
    grant_difference,
    grant_restriction,
    grant_union,
)
from responsibleai.formula.authority.creation import (
    AuthorityCreationEvent,
    apply_creation_event,
    apply_delegation,
    issuer_can_grant,
    validate_creation_event,
)
from responsibleai.formula.authority.delegation import DelegationChain
from responsibleai.formula.authority.lifecycle import (
    assert_grant_usable,
    consume_grant,
    lifecycle_at,
)
from responsibleai.formula.authority.models import (
    AuthorityConstraint,
    AuthorityGrant,
    AuthorityLifecycle,
    AuthoritySubject,
    ExplicitDeny,
    OrgAuthorityCeilingModel,
)
from responsibleai.formula.authority.root import TenantRootPrincipal
from responsibleai.formula.authority.tenant import (
    validate_ceiling_tenant,
    validate_creation_event_tenant,
    validate_deny_tenant,
    validate_grant_tenant,
)
from responsibleai.formula.authority.wildcard import WILDCARD
from responsibleai.formula.epistemic import EpistemicStatus
from responsibleai.formula.errors import (
    AuthorityExpansion,
    ConsumedGrant,
    CrossTenantReference,
    InvalidGrant,
    VersionMismatch,
)
from responsibleai.formula.fence import CommitFence, EvaluationPin
from responsibleai.formula.graph.elements import GraphNode
from responsibleai.formula.graph.graph import CanonicalAISystemGraph
from responsibleai.formula.graph.kinds import NodeKind
from responsibleai.formula.immutability import freeze_mapping, freeze_value
from responsibleai.formula.invariants import FormulaInvariantChecker, InvariantId
from responsibleai.formula.serialization import (
    canonical_encode,
    serialize_authority_evaluation,
    serialize_grant,
    serialize_graph_snapshot,
    serialize_trace,
    utc_iso,
)
from responsibleai.formula.trace.semantics import TraceAuthorized
from responsibleai.formula.trace.trace import FormulaTrace, FormulaTraceEvent, TransitionClass


def _creation_event(
    grant: AuthorityGrant,
    *,
    at: datetime | None = None,
    evidence_ref: str = "ev-event",
    policy_version: str = "pol-1",
    issuer_id: str | None = None,
    subject_id: str | None = None,
) -> AuthorityCreationEvent:
    return AuthorityCreationEvent(
        issuer_id=issuer_id or grant.issuer_id,
        subject_id=subject_id or grant.subject.subject_id,
        new_grant=grant,
        reason="test",
        at=at or grant.not_before,
        evidence_ref=evidence_ref,
        policy_version=policy_version,
    )


def test_validate_creation_event_rejects_missing_fields() -> None:
    g = make_grant("g", "s")
    with pytest.raises(InvalidGrant, match="evidence_ref"):
        validate_creation_event(_creation_event(g, evidence_ref=""))
    with pytest.raises(InvalidGrant, match="policy_version"):
        validate_creation_event(_creation_event(g, policy_version=""))
    with pytest.raises(CrossTenantReference, match="issuer"):
        validate_creation_event(_creation_event(g, issuer_id="other"))
    with pytest.raises(CrossTenantReference, match="subject"):
        validate_creation_event(_creation_event(g, subject_id="other"))
    with pytest.raises(InvalidGrant, match="not_before"):
        validate_creation_event(_creation_event(g, at=g.not_before - timedelta(seconds=1)))
    with pytest.raises(InvalidGrant, match="expiry"):
        validate_creation_event(_creation_event(g, at=g.expires_at))


def test_apply_creation_event_pending_promotion_and_failures() -> None:
    g = make_grant("g", "s", lifecycle=AuthorityLifecycle.PENDING)
    ev = _creation_event(g)
    root = TenantRootPrincipal("t1", "issuer-root", "org", "ev-root", "pol-1")
    state = apply_creation_event((), ev, EffectiveAuthorityEvaluator(), root=root)
    assert state[0].lifecycle == AuthorityLifecycle.ACTIVE

    revoked = make_grant("r", "s2", lifecycle=AuthorityLifecycle.REVOKED)
    with pytest.raises(InvalidGrant):
        apply_creation_event(
            (),
            _creation_event(revoked),
            EffectiveAuthorityEvaluator(),
            root=TenantRootPrincipal("t1", "issuer-root", "org", "ev", "pol"),
        )

    broad = make_grant("b", "s3", risk=9, issuer_id="issuer-root")
    with pytest.raises(AuthorityExpansion):
        apply_creation_event((), _creation_event(broad), EffectiveAuthorityEvaluator())


def test_issuer_can_grant_edge_paths() -> None:
    g = make_grant("g", "s", issuer_id="issuer")
    assert not issuer_can_grant("wrong", g, (), EffectiveAuthorityEvaluator(), g.not_before)
    self_grant = make_grant("sg", "issuer", issuer_id="issuer")
    assert not issuer_can_grant(
        "issuer", self_grant, (), EffectiveAuthorityEvaluator(), g.not_before
    )

    root = TenantRootPrincipal("t1", "root-1", "org", "ev", "pol", ceiling=None)
    ok = make_grant("ok", "agent", issuer_id="root-1")
    assert issuer_can_grant(
        "root-1", ok, (), EffectiveAuthorityEvaluator(), ok.not_before, root=root
    )

    ceiling = OrgAuthorityCeilingModel(
        tenant_id="t1", org_id="o1", allowed_actions=frozenset({"read"}), max_risk_class=5
    )
    root_with_ceiling = TenantRootPrincipal("t1", "root-2", "org", "ev", "pol", ceiling=ceiling)
    ok2 = make_grant("ok2", "agent2", issuer_id="root-2")
    assert issuer_can_grant(
        "root-2",
        ok2,
        (),
        EffectiveAuthorityEvaluator(ceiling=ceiling),
        ok2.not_before,
        root=root_with_ceiling,
    )


def test_grant_contained_in_issuer_authority_branches() -> None:
    issuer_g = make_grant("ig", "issuer", actions=frozenset({"read"}))
    child = make_grant("c", "agent", actions=frozenset({"read"}), issuer_id="issuer")
    at = issuer_g.not_before
    assert grant_contained_in_issuer_authority(child, (issuer_g,), at, "issuer")
    assert not grant_contained_in_issuer_authority(
        make_grant("x", "agent", actions=frozenset({"write"}), issuer_id="issuer"),
        (issuer_g,),
        at,
        "issuer",
    )


def test_apply_delegation_delegator_mismatch() -> None:
    parent = make_grant("p", "org", allow_delegation=True)
    child = make_grant("c", "agent", delegator="wrong")
    with pytest.raises(InvalidGrant, match="delegator_id"):
        apply_delegation(parent, child)


def test_tenant_validation_helpers() -> None:
    g = make_grant("g", "s")
    validate_grant_tenant(g)
    bad = AuthorityGrant(
        grant_id="b",
        tenant_id="t1",
        subject=AuthoritySubject("s", "t2"),
        issuer_id="i",
        delegator_id=None,
        actions=frozenset({"read"}),
        resources=frozenset({"x"}),
        purposes=frozenset({"ops"}),
        not_before=g.not_before,
        expires_at=g.expires_at,
        risk_ceiling=5,
        constraints=AuthorityConstraint(),
        evidence_ref="ev",
    )
    with pytest.raises(CrossTenantReference):
        validate_grant_tenant(bad)

    deny = ExplicitDeny("d", "t2", "s", frozenset({"read"}), frozenset({"x"}))
    with pytest.raises(CrossTenantReference):
        validate_deny_tenant(deny, "t1")

    ceiling = OrgAuthorityCeilingModel(
        tenant_id="t2", org_id="o", allowed_actions=frozenset({"read"}), max_risk_class=5
    )
    with pytest.raises(CrossTenantReference):
        validate_ceiling_tenant(ceiling, "t1")

    with pytest.raises(TypeError):
        validate_creation_event_tenant(object())


def test_lifecycle_superseded_and_consume_errors() -> None:
    g = make_grant("g", "s", lifecycle=AuthorityLifecycle.SUPERSEDED)
    assert lifecycle_at(g, g.not_before) == AuthorityLifecycle.SUPERSEDED
    with pytest.raises(ConsumedGrant):
        assert_grant_usable(g, g.not_before)
    with pytest.raises(ConsumedGrant, match="not consumable"):
        consume_grant(make_grant("nc", "s", one_shot=False))


def test_grant_restriction_and_denies_branches() -> None:
    g = make_grant("g", "s", actions=frozenset({"read", "write"}), risk=9)
    tuples = grant_union((g,))
    ceiling = OrgAuthorityCeilingModel(
        tenant_id="t1",
        org_id="o1",
        allowed_actions=frozenset({"read"}),
        allowed_resources=frozenset({"x"}),
        max_risk_class=3,
    )
    restricted = grant_restriction(tuples, ceiling)
    assert restricted == frozenset() or all(t.risk_ceiling <= 3 for t in restricted)

    at = g.not_before
    deny_other = ExplicitDeny("d1", "t2", "s", frozenset({"read"}), frozenset({"x"}))
    deny_subject = ExplicitDeny("d2", "t1", "other", frozenset({"read"}), frozenset({"x"}))
    expired_deny = ExplicitDeny(
        "d3",
        "t1",
        "s",
        frozenset({"read"}),
        frozenset({"x"}),
        expires_at=at - timedelta(seconds=1),
    )
    out = apply_explicit_denies(tuples, (deny_other, deny_subject, expired_deny), "s", "t1", at)
    assert out == tuples

    wildcard_deny = ExplicitDeny("d4", "t1", "s", frozenset({WILDCARD}), frozenset({WILDCARD}))
    out2 = apply_explicit_denies(tuples, (wildcard_deny,), "s", "t1", at)
    assert out2 == frozenset()


def test_effective_ceiling_tenant_mismatch() -> None:
    g = make_grant("g", "s")
    ceiling = OrgAuthorityCeilingModel(
        tenant_id="t2", org_id="o", allowed_actions=frozenset({"read"}), max_risk_class=5
    )
    ev = EffectiveAuthorityEvaluator(ceiling=ceiling)
    with pytest.raises(CrossTenantReference):
        ev.effective((g,), (), "s", "t1", g.not_before)


def test_invariant_checker_branches() -> None:
    checker = FormulaInvariantChecker()
    unknown = make_grant("u", "s")
    unknown = AuthorityGrant(
        grant_id=unknown.grant_id,
        tenant_id=unknown.tenant_id,
        subject=unknown.subject,
        issuer_id=unknown.issuer_id,
        delegator_id=unknown.delegator_id,
        actions=unknown.actions,
        resources=unknown.resources,
        purposes=unknown.purposes,
        context=unknown.context,
        not_before=unknown.not_before,
        expires_at=unknown.expires_at,
        risk_ceiling=unknown.risk_ceiling,
        constraints=unknown.constraints,
        lifecycle=unknown.lifecycle,
        evidence_ref=unknown.evidence_ref,
        epistemic_status=EpistemicStatus.UNKNOWN,
        schema_version=unknown.schema_version,
        version=unknown.version,
    )
    v = checker.check_unknown_not_authority(unknown, authorize_execute=True)
    assert v and v[0].invariant == InvariantId.INV_UNKNOWN_NOT_AUTHORITY

    assert checker.check_tenant("a", "b")
    chain = DelegationChain((make_grant("a", "x"), make_grant("b", "y", delegator="x")))
    assert checker.check_delegation_chain(chain)

    pin = EvaluationPin("e1", "0.1.0", 1, 1, "pol")
    fence = CommitFence(1, 1)
    violations = checker.check_version_pin(pin, fence, 2, 1)
    assert violations and violations[0].invariant == InvariantId.INV_VERSION_PINNING

    parent = make_grant("p", "org", allow_delegation=True)
    child = make_grant("c", "agent", delegator="org", risk=99)
    assert checker.check_parent_child_subset(parent, child)

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
        (),
        TransitionClass.DETERMINISTIC,
        "h0",
        "h1",
    )
    trace = FormulaTrace("t1", (ev,), "0.1.0", "0.1.0")
    assert checker.check_trace_authority(trace, frozenset({"e2"}))

    g = make_grant("g", "s")
    ceiling = OrgAuthorityCeilingModel(
        tenant_id="t1", org_id="o1", allowed_actions=frozenset({"read"}), max_risk_class=5
    )
    assert checker.check_org_ceiling((g,), ceiling, g.not_before, "s", "t1") == []


def test_serialization_and_immutability_branches() -> None:
    g = make_grant("g", "s")
    assert serialize_grant(g)["grant_id"] == "g"
    naive = datetime(2026, 1, 1, 12, 0, 0)
    assert utc_iso(naive).endswith("Z")
    assert canonical_encode(frozenset({1, 2})) == [1, 2]
    assert canonical_encode([1, 2]) == [1, 2]
    with pytest.raises(TypeError):
        canonical_encode(object())

    assert freeze_value({"a": 1}) == (("a", 1),)
    assert freeze_value([1, 2]) == (1, 2)
    assert freeze_value({1, 2}) == (1, 2)
    assert freeze_mapping({"z": 1, "a": freeze_value((1, 2))})
    with pytest.raises(TypeError):
        freeze_value(object())

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
        (),
        (),
        TransitionClass.DETERMINISTIC,
        "h0",
        "h1",
    )
    trace = FormulaTrace("t1", (ev,), "0.1.0", "0.1.0")
    assert serialize_trace(trace)["tenant_id"] == "t1"

    tuples = grant_union((g,))
    ser = serialize_authority_evaluation(tuples, EffectiveAuthorityEvaluator(), "s", "t1")
    assert ser["subject_id"] == "s"

    graph = CanonicalAISystemGraph("t1")
    graph.add_node(GraphNode.build("n1", "t1", NodeKind.AGENT))
    snap = graph.freeze()
    assert serialize_graph_snapshot(snap)["content_hash"] == snap.content_hash


def test_delegation_chain_and_grant_difference() -> None:
    parent = make_grant("p", "org", allow_delegation=True)
    child = make_grant("c", "agent", delegator="org")
    chain = DelegationChain((parent, child))
    assert chain.root_effective_subset() is True
    chain.validate()

    bad = DelegationChain(
        (parent, make_grant("c2", "agent", delegator="org", actions=frozenset({WILDCARD})))
    )
    assert bad.root_effective_subset() is False
    assert FormulaInvariantChecker().check_delegation_chain(bad)

    u = grant_union((parent,))
    diff = grant_difference(u, frozenset())
    assert diff == u


def test_trace_authorized_predicate() -> None:
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
        (),
        (),
        TransitionClass.DETERMINISTIC,
        "h0",
        "h1",
    )
    trace = FormulaTrace("t1", (ev,), "0.1.0", "0.1.0")
    assert TraceAuthorized(trace, frozenset({"e1"})) is True
    assert TraceAuthorized(trace, frozenset()) is False


def test_fence_version_mismatch() -> None:
    pin = EvaluationPin("e1", "0.1.0", 1, 1, "pol")
    fence = CommitFence(1, 1)
    with pytest.raises(VersionMismatch):
        fence.validate(pin, 2, 1)
    with pytest.raises(VersionMismatch):
        fence.validate(pin, 1, 2)
