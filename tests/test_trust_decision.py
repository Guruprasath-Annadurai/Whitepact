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
