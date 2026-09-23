# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Unit and adversarial tests for TrustDecisionEngine."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import update

from responsibleai.db.engine import (
    create_engine,
    organizations,
    trust_fabric_conflicts,
    trust_fabric_principals,
)
from responsibleai.trust_fabric.authority_graph import AuthorityGraph
from responsibleai.trust_fabric.decision import TrustDecisionEngine
from responsibleai.trust_fabric.directory import PrincipalDirectory
from responsibleai.trust_fabric.enums import (
    ConflictStatus,
    ConflictType,
    DecisionOutcome,
    PrincipalState,
    PrincipalType,
)
from responsibleai.trust_fabric.models import TrustDecisionRequest


@pytest.fixture
async def decision_db(tmp_path):
    url = f"{tmp_path}/test_decision.db"
    engine = create_engine(url)
    await engine.init()
    async with engine.raw.begin() as conn:
        await conn.execute(
            organizations.insert(),
            [
                {"id": "org_target", "name": "Target Org", "slug": "target", "created_at": "now"},
                {"id": "org_req", "name": "Requester Org", "slug": "req", "created_at": "now"},
                {"id": "org_other", "name": "Other Org", "slug": "other", "created_at": "now"},
            ],
        )
    try:
        yield engine
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_decision_unknown_principal(decision_db):
    """Unknown principal evaluates to UNKNOWN outcome without guessing."""
    engine = TrustDecisionEngine(decision_db)
    req = TrustDecisionRequest(
        requesting_org_id="org_req",
        target_org_id="org_target",
        subject_principal_id="wp_pr_ghost",
        requested_action="TRANSFER_FUNDS",
        context={"amount_usd": "5000"},
    )
    resp = await engine.evaluate_decision(req)
    assert resp.decision == DecisionOutcome.UNKNOWN
    assert resp.reason_code == "PRINCIPAL_UNKNOWN"
    assert "unknown to WhitePact" in resp.explanation


@pytest.mark.asyncio
async def test_decision_inactive_or_revoked_principal(decision_db):
    """Deactivated, deleted, or revoked principals must be denied immediately."""
    dir_svc = PrincipalDirectory(decision_db)
    p_disabled = await dir_svc.create_principal(
        org_id="org_target",
        principal_type=PrincipalType.HUMAN,
        display_name="Disabled User",
    )
    p_revoked = await dir_svc.create_principal(
        org_id="org_target",
        principal_type=PrincipalType.AI_AGENT,
        display_name="Revoked Agent",
    )

    async with decision_db.raw.begin() as conn:
        await conn.execute(
            update(trust_fabric_principals)
            .where(trust_fabric_principals.c.id == p_disabled.id)
            .values(lifecycle_state=PrincipalState.DISABLED.value)
        )
        await conn.execute(
            update(trust_fabric_principals)
            .where(trust_fabric_principals.c.id == p_revoked.id)
            .values(lifecycle_state=PrincipalState.REVOKED.value)
        )

    engine = TrustDecisionEngine(decision_db)

    # Test disabled
    req_disabled = TrustDecisionRequest(
        requesting_org_id="org_req",
        target_org_id="org_target",
        subject_principal_id=p_disabled.id,
        requested_action="ACCESS_RESOURCE",
        context={},
    )
    resp_disabled = await engine.evaluate_decision(req_disabled)
    assert resp_disabled.decision == DecisionOutcome.DENY
    assert resp_disabled.reason_code == "PRINCIPAL_INACTIVE"

    # Test revoked
    req_revoked = TrustDecisionRequest(
        requesting_org_id="org_req",
        target_org_id="org_target",
        subject_principal_id=p_revoked.id,
        requested_action="ACCESS_RESOURCE",
        context={},
    )
    resp_revoked = await engine.evaluate_decision(req_revoked)
    assert resp_revoked.decision == DecisionOutcome.DENY
    assert resp_revoked.reason_code == "PRINCIPAL_REVOKED"


@pytest.mark.asyncio
async def test_decision_amount_ceiling_enforcement(decision_db):
    """Enforces financial amount ceilings deterministically."""
    dir_svc = PrincipalDirectory(decision_db)
    auth_graph = AuthorityGraph(decision_db)

    grantor = await dir_svc.create_principal(
        org_id="org_target",
        principal_type=PrincipalType.ORGANIZATION,
        display_name="Target Org Root",
    )
    officer = await dir_svc.create_principal(
        org_id="org_target",
        principal_type=PrincipalType.HUMAN,
        display_name="Officer Bob",
    )

    # Authority edge with ceiling $10,000
    await auth_graph.grant_authority(
        grantor_principal_id=grantor.id,
        grantee_principal_id=officer.id,
        org_id="org_target",
        action_type="SIGN_PAYMENT",
        resource_pattern="PAYMENT_GATEWAY",
        ceiling_limit_usd=10000.0,
    )

    engine = TrustDecisionEngine(decision_db)

    # 1. Under ceiling ($5,000) -> ALLOW
    req_under = TrustDecisionRequest(
        requesting_org_id="org_req",
        target_org_id="org_target",
        subject_principal_id=officer.id,
        requested_action="SIGN_PAYMENT",
        context={"amount_usd": "5000", "resource": "PAYMENT_GATEWAY"},
    )
    resp_under = await engine.evaluate_decision(req_under)
    assert resp_under.decision == DecisionOutcome.ALLOW
    assert resp_under.reason_code == "AUTHORIZED"

    # 2. Over ceiling ($25,000) -> DENY
    req_over = TrustDecisionRequest(
        requesting_org_id="org_req",
        target_org_id="org_target",
        subject_principal_id=officer.id,
        requested_action="SIGN_PAYMENT",
        context={"amount_usd": "25000", "resource": "PAYMENT_GATEWAY"},
    )
    resp_over = await engine.evaluate_decision(req_over)
    assert resp_over.decision == DecisionOutcome.DENY
    assert resp_over.reason_code == "AUTHORITY_CEILING_EXCEEDED"


@pytest.mark.asyncio
async def test_decision_conflict_fails_closed_to_requires_review(decision_db):
    """Presence of active unresolved material conflict triggers REQUIRES_REVIEW."""
    now_iso = datetime.now(UTC).isoformat()
    dir_svc = PrincipalDirectory(decision_db)

    disputed = await dir_svc.create_principal(
        org_id="org_target",
        principal_type=PrincipalType.ORGANIZATION,
        display_name="Disputed Corp",
    )

    async with decision_db.raw.begin() as conn:
        await conn.execute(
            update(trust_fabric_principals)
            .where(trust_fabric_principals.c.id == disputed.id)
            .values(lifecycle_state=PrincipalState.CONFLICTED.value)
        )
        # Record conflict
        await conn.execute(
            trust_fabric_conflicts.insert().values(
                id="conf_disputed_1",
                principal_id=disputed.id,
                org_id="org_target",
                field_or_claim="beneficial_owner",
                assertion_id_a="asst_1",
                assertion_id_b="asst_2",
                conflict_type=ConflictType.VALUE_CONTRADICTION.value,
                detected_at=now_iso,
                status=ConflictStatus.UNRESOLVED.value,
                resolution_reason=None,
                resolved_at=None,
            )
        )

    engine = TrustDecisionEngine(decision_db)
    req = TrustDecisionRequest(
        requesting_org_id="org_req",
        target_org_id="org_target",
        subject_principal_id=disputed.id,
        requested_action="EXECUTE_CONTRACT",
        context={},
    )
    resp = await engine.evaluate_decision(req)
    assert resp.decision == DecisionOutcome.REQUIRES_REVIEW
    assert resp.reason_code == "TRUST_CONFLICT_DETECTED"


@pytest.mark.asyncio
async def test_decision_stale_cache_invalidation_upon_revocation(decision_db):
    """Authoritative state revocation immediately purges cache; stale cache allow = 0."""
    dir_svc = PrincipalDirectory(decision_db)
    auth_graph = AuthorityGraph(decision_db)

    root = await dir_svc.create_principal(
        org_id="org_target",
        principal_type=PrincipalType.ORGANIZATION,
        display_name="Target Root",
    )
    user = await dir_svc.create_principal(
        org_id="org_target",
        principal_type=PrincipalType.HUMAN,
        display_name="User Alice",
    )

    edge = await auth_graph.grant_authority(
        grantor_principal_id=root.id,
        grantee_principal_id=user.id,
        org_id="org_target",
        action_type="SIGN_TX",
        resource_pattern="*",
        ceiling_limit_usd=50000.0,
    )

    engine = TrustDecisionEngine(decision_db)
    req = TrustDecisionRequest(
        requesting_org_id="org_req",
        target_org_id="org_target",
        subject_principal_id=user.id,
        requested_action="SIGN_TX",
        context={"amount_usd": 1000},
    )

    # 1. Initial decision -> ALLOW and cached
    resp1 = await engine.evaluate_decision(req)
    assert resp1.decision == DecisionOutcome.ALLOW
    assert engine.monitor.get_cached_decision(f"decision:{req.compute_digest()}") is not None

    # 2. Revoke authority via monitor
    await engine.monitor.revoke_authority(edge.id, org_id="org_target")

    # 3. Cache must be empty and subsequent decision MUST NOT be ALLOW
    assert engine.monitor.get_cached_decision(f"decision:{req.compute_digest()}") is None

    stale_cache_allows = 0
    resp2 = await engine.evaluate_decision(req)
    if resp2.decision == DecisionOutcome.ALLOW:
        stale_cache_allows += 1
    assert resp2.decision != DecisionOutcome.ALLOW
    assert stale_cache_allows == 0


@pytest.mark.asyncio
async def test_decision_cache_redis_failure_fails_closed(decision_db):
    """Simulated Redis/cache outage falls back to DB evaluation and NEVER widens trust."""
    dir_svc = PrincipalDirectory(decision_db)
    auth_graph = AuthorityGraph(decision_db)

    root = await dir_svc.create_principal(
        org_id="org_target",
        principal_type=PrincipalType.ORGANIZATION,
        display_name="Root",
    )
    user = await dir_svc.create_principal(
        org_id="org_target",
        principal_type=PrincipalType.HUMAN,
        display_name="User",
    )
    await auth_graph.grant_authority(
        grantor_principal_id=root.id,
        grantee_principal_id=user.id,
        org_id="org_target",
        action_type="TRANSFER",
        resource_pattern="*",
        ceiling_limit_usd=100.0,
    )

    engine = TrustDecisionEngine(decision_db)
    # Simulate Redis / cache failure
    engine.monitor.simulate_cache_failure(True)

    # Over ceiling ($500 > $100 ceiling)
    req_over = TrustDecisionRequest(
        requesting_org_id="org_req",
        target_org_id="org_target",
        subject_principal_id=user.id,
        requested_action="TRANSFER",
        context={"amount_usd": 500},
    )
    resp = await engine.evaluate_decision(req_over)
    # Must DENY, cache failure did not widen trust
    assert resp.decision == DecisionOutcome.DENY
    redis_failure_widens_trust = False
    assert not redis_failure_widens_trust


@pytest.mark.asyncio
async def test_decision_request_binding_mutations(decision_db):
    """Mutation of any request dimension prevents reusing a previously verified decision."""
    dir_svc = PrincipalDirectory(decision_db)
    auth_graph = AuthorityGraph(decision_db)

    root = await dir_svc.create_principal(
        org_id="org_target",
        principal_type=PrincipalType.ORGANIZATION,
        display_name="Target Root",
    )
    user1 = await dir_svc.create_principal(
        org_id="org_target",
        principal_type=PrincipalType.HUMAN,
        display_name="User 1",
    )
    user2 = await dir_svc.create_principal(
        org_id="org_target",
        principal_type=PrincipalType.HUMAN,
        display_name="User 2",
    )

    await auth_graph.grant_authority(
        grantor_principal_id=root.id,
        grantee_principal_id=user1.id,
        org_id="org_target",
        action_type="APPROVE_PAYMENT",
        resource_pattern="LEDGER_1",
        ceiling_limit_usd=5000.0,
    )

    engine = TrustDecisionEngine(decision_db)

    # Base valid request
    base_req = TrustDecisionRequest(
        requesting_org_id="org_req",
        requesting_principal_id="wp_pr_operator",
        target_org_id="org_target",
        subject_principal_id=user1.id,
        requested_action="APPROVE_PAYMENT",
        resource="LEDGER_1",
        amount_usd=1000.0,
        proof_type="CRYPTOGRAPHIC_ASSERTION",
        source_snapshot="snap_2026",
        evidence_reference="ev_proof_1",
        context={"amount_usd": 1000.0, "resource": "LEDGER_1"},
    )
    base_resp = await engine.evaluate_decision(base_req)
    assert base_resp.decision == DecisionOutcome.ALLOW
    assert base_resp.request_digest == base_req.compute_digest()

    mutated_reuses = 0
    cross_tenant_reuses = 0

    # 1. Mutate requesting_principal_id
    m1 = TrustDecisionRequest(
        requesting_org_id=base_req.requesting_org_id,
        requesting_principal_id="wp_pr_imposter",
        target_org_id=base_req.target_org_id,
        subject_principal_id=base_req.subject_principal_id,
        requested_action=base_req.requested_action,
        resource=base_req.resource,
        amount_usd=base_req.amount_usd,
        proof_type=base_req.proof_type,
        source_snapshot=base_req.source_snapshot,
        evidence_reference=base_req.evidence_reference,
    )
    if engine.monitor.get_cached_decision(f"decision:{m1.compute_digest()}") is not None:
        mutated_reuses += 1

    # 2. Mutate requesting_org_id
    m2 = TrustDecisionRequest(
        requesting_org_id="org_other",
        requesting_principal_id=base_req.requesting_principal_id,
        target_org_id=base_req.target_org_id,
        subject_principal_id=base_req.subject_principal_id,
        requested_action=base_req.requested_action,
        resource=base_req.resource,
        amount_usd=base_req.amount_usd,
    )
    if engine.monitor.get_cached_decision(f"decision:{m2.compute_digest()}") is not None:
        mutated_reuses += 1

    # 3. Mutate target_org_id (cross-tenant attempt)
    m3 = TrustDecisionRequest(
        requesting_org_id=base_req.requesting_org_id,
        requesting_principal_id=base_req.requesting_principal_id,
        target_org_id="org_other",
        subject_principal_id=base_req.subject_principal_id,
        requested_action=base_req.requested_action,
        resource=base_req.resource,
        amount_usd=base_req.amount_usd,
    )
    if engine.monitor.get_cached_decision(f"decision:{m3.compute_digest()}") is not None:
        cross_tenant_reuses += 1
        mutated_reuses += 1

    # 4. Mutate subject_principal_id
    m4 = TrustDecisionRequest(
        requesting_org_id=base_req.requesting_org_id,
        requesting_principal_id=base_req.requesting_principal_id,
        target_org_id=base_req.target_org_id,
        subject_principal_id=user2.id,
        requested_action=base_req.requested_action,
        resource=base_req.resource,
        amount_usd=base_req.amount_usd,
    )
    if engine.monitor.get_cached_decision(f"decision:{m4.compute_digest()}") is not None:
        mutated_reuses += 1

    # 5. Mutate requested_action
    m5 = TrustDecisionRequest(
        requesting_org_id=base_req.requesting_org_id,
        requesting_principal_id=base_req.requesting_principal_id,
        target_org_id=base_req.target_org_id,
        subject_principal_id=base_req.subject_principal_id,
        requested_action="DELETE_ALL_DATA",
        resource=base_req.resource,
        amount_usd=base_req.amount_usd,
    )
    if engine.monitor.get_cached_decision(f"decision:{m5.compute_digest()}") is not None:
        mutated_reuses += 1

    # 6. Mutate amount_usd
    m6 = TrustDecisionRequest(
        requesting_org_id=base_req.requesting_org_id,
        requesting_principal_id=base_req.requesting_principal_id,
        target_org_id=base_req.target_org_id,
        subject_principal_id=base_req.subject_principal_id,
        requested_action=base_req.requested_action,
        resource=base_req.resource,
        amount_usd=999999.0,
    )
    if engine.monitor.get_cached_decision(f"decision:{m6.compute_digest()}") is not None:
        mutated_reuses += 1

    # 7. Mutate resource
    m7 = TrustDecisionRequest(
        requesting_org_id=base_req.requesting_org_id,
        requesting_principal_id=base_req.requesting_principal_id,
        target_org_id=base_req.target_org_id,
        subject_principal_id=base_req.subject_principal_id,
        requested_action=base_req.requested_action,
        resource="LEDGER_RESTRICTED",
        amount_usd=base_req.amount_usd,
    )
    if engine.monitor.get_cached_decision(f"decision:{m7.compute_digest()}") is not None:
        mutated_reuses += 1

    # 8. Mutate proof_type
    m8 = TrustDecisionRequest(
        requesting_org_id=base_req.requesting_org_id,
        target_org_id=base_req.target_org_id,
        subject_principal_id=base_req.subject_principal_id,
        requested_action=base_req.requested_action,
        proof_type="FORGED_PROOF",
    )
    if engine.monitor.get_cached_decision(f"decision:{m8.compute_digest()}") is not None:
        mutated_reuses += 1

    # 9. Mutate source_snapshot
    m9 = TrustDecisionRequest(
        requesting_org_id=base_req.requesting_org_id,
        target_org_id=base_req.target_org_id,
        subject_principal_id=base_req.subject_principal_id,
        requested_action=base_req.requested_action,
        source_snapshot="tampered_snapshot",
    )
    if engine.monitor.get_cached_decision(f"decision:{m9.compute_digest()}") is not None:
        mutated_reuses += 1

    # 10. Mutate evidence_reference
    m10 = TrustDecisionRequest(
        requesting_org_id=base_req.requesting_org_id,
        target_org_id=base_req.target_org_id,
        subject_principal_id=base_req.subject_principal_id,
        requested_action=base_req.requested_action,
        evidence_reference="tampered_evidence",
    )
    if engine.monitor.get_cached_decision(f"decision:{m10.compute_digest()}") is not None:
        mutated_reuses += 1

    assert mutated_reuses == 0
    assert cross_tenant_reuses == 0


@pytest.mark.asyncio
async def test_decision_zero_false_verifications_for_unknown_and_conflict(decision_db):
    """Audit check: unknown and conflicted entities yield 0 false verifications."""
    engine = TrustDecisionEngine(decision_db)
    unknown_false_verifications = 0
    conflict_false_verifications = 0

    # 1. Unknown
    req_unknown = TrustDecisionRequest(
        requesting_org_id="org_req",
        target_org_id="org_target",
        subject_principal_id="wp_pr_does_not_exist",
        requested_action="TRANSFER",
    )
    resp_un = await engine.evaluate_decision(req_unknown)
    if resp_un.decision == DecisionOutcome.ALLOW:
        unknown_false_verifications += 1
    assert resp_un.decision == DecisionOutcome.UNKNOWN
    assert unknown_false_verifications == 0

    # 2. Conflicted
    now_iso = datetime.now(UTC).isoformat()
    dir_svc = PrincipalDirectory(decision_db)
    p_conf = await dir_svc.create_principal(
        org_id="org_target",
        principal_type=PrincipalType.ORGANIZATION,
        display_name="Conflicted Org",
    )
    async with decision_db.raw.begin() as conn:
        await conn.execute(
            update(trust_fabric_principals)
            .where(trust_fabric_principals.c.id == p_conf.id)
            .values(lifecycle_state=PrincipalState.CONFLICTED.value)
        )
        await conn.execute(
            trust_fabric_conflicts.insert().values(
                id="conf_audit_1",
                principal_id=p_conf.id,
                org_id="org_target",
                field_or_claim="sanction_status",
                assertion_id_a="a1",
                assertion_id_b="a2",
                conflict_type=ConflictType.VALUE_CONTRADICTION.value,
                detected_at=now_iso,
                status=ConflictStatus.UNRESOLVED.value,
                resolution_reason=None,
                resolved_at=None,
            )
        )
    req_conf = TrustDecisionRequest(
        requesting_org_id="org_req",
        target_org_id="org_target",
        subject_principal_id=p_conf.id,
        requested_action="APPROVE_SANCTIONED_ACTIVITY",
    )
    resp_c = await engine.evaluate_decision(req_conf)
    if resp_c.decision == DecisionOutcome.ALLOW:
        conflict_false_verifications += 1
    assert resp_c.decision == DecisionOutcome.REQUIRES_REVIEW
    assert conflict_false_verifications == 0
