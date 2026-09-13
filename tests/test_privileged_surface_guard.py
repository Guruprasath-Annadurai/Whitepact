# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Unit and Contract Tests for PrivilegedSurfaceGuard & Canonical Chokepoint."""

from __future__ import annotations

import pytest
from sqlalchemy import insert

from responsibleai.db.engine import DatabaseEngine, create_engine, org_api_keys, organizations
from responsibleai.iam.enums import (
    PrivilegedAction,
    PrivilegeRiskTier,
    StepUpMethod,
)
from responsibleai.iam.errors import (
    CrossTenantEscalationError,
    FourEyesRequiredError,
    OperatorBackdoorAttemptError,
    PrivilegedAccessDeniedError,
    StepUpRequiredError,
)
from responsibleai.iam.guard import PrivilegedSurfaceGuard
from responsibleai.iam.models import PrivilegedCallerContext, StepUpProof
from responsibleai.rbac.models import Role


@pytest.fixture
async def test_db():
    engine = create_engine(":memory:")
    await engine.init()
    # Seed organizations
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id="org_alpha",
                name="Alpha Corp",
                slug="alpha-corp",
                monthly_budget_usd=10000.0,
                created_at="2026-09-12T00:00:00Z",
                plan="ENTERPRISE",
            )
        )
        await conn.execute(
            insert(organizations).values(
                id="org_beta",
                name="Beta Corp",
                slug="beta-corp",
                monthly_budget_usd=10000.0,
                created_at="2026-09-12T00:00:00Z",
                plan="ENTERPRISE",
            )
        )
        await conn.execute(
            insert(org_api_keys).values(
                id="key_admin",
                org_id="org_alpha",
                name="admin-key",
                role="ADMIN",
                key_hash="hash_admin",
                created_at="2026-09-12T00:00:00Z",
                revoked=0,
                mfa_enrolled=0,
            )
        )
    yield engine
    await engine.close()


@pytest.mark.asyncio
async def test_platform_operator_backdoor_blocked(test_db: DatabaseEngine):
    guard = PrivilegedSurfaceGuard(test_db)
    caller = PrivilegedCallerContext(
        principal_id="wp_operator_001",
        org_id="org_alpha",
        role=Role.OWNER,
        is_platform_operator=True,
    )
    with pytest.raises(OperatorBackdoorAttemptError, match="cannot execute customer tenant privileged actions"):
        await guard.authorize_privileged_operation(
            caller=caller,
            target_org_id="org_alpha",
            action=PrivilegedAction.CREATE_API_KEY,
        )


@pytest.mark.asyncio
async def test_cross_tenant_escalation_blocked(test_db: DatabaseEngine):
    guard = PrivilegedSurfaceGuard(test_db)
    caller = PrivilegedCallerContext(
        principal_id="user_alpha",
        org_id="org_alpha",
        role=Role.ADMIN,
    )
    with pytest.raises(CrossTenantEscalationError, match="cannot execute privileged actions on tenant 'org_beta'"):
        await guard.authorize_privileged_operation(
            caller=caller,
            target_org_id="org_beta",
            action=PrivilegedAction.CREATE_API_KEY,
        )


@pytest.mark.asyncio
async def test_unprivileged_role_denied(test_db: DatabaseEngine):
    guard = PrivilegedSurfaceGuard(test_db)
    caller = PrivilegedCallerContext(
        principal_id="viewer_alpha",
        org_id="org_alpha",
        role=Role.VIEWER,
    )
    with pytest.raises(PrivilegedAccessDeniedError, match="requires ADMIN or OWNER role"):
        await guard.authorize_privileged_operation(
            caller=caller,
            target_org_id="org_alpha",
            action=PrivilegedAction.CREATE_API_KEY,
        )


@pytest.mark.asyncio
async def test_standard_privileged_action_allowed_for_admin(test_db: DatabaseEngine):
    guard = PrivilegedSurfaceGuard(test_db)
    caller = PrivilegedCallerContext(
        principal_id="admin_alpha",
        org_id="org_alpha",
        role=Role.ADMIN,
    )
    res = await guard.authorize_privileged_operation(
        caller=caller,
        target_org_id="org_alpha",
        action=PrivilegedAction.CREATE_API_KEY,
    )
    assert res.allowed is True
    assert res.risk_tier == PrivilegeRiskTier.PRIVILEGED_STANDARD
    assert res.audit_hash != ""


@pytest.mark.asyncio
async def test_high_risk_requires_step_up_nonce(test_db: DatabaseEngine):
    guard = PrivilegedSurfaceGuard(test_db)
    caller = PrivilegedCallerContext(
        principal_id="admin_alpha",
        org_id="org_alpha",
        role=Role.ADMIN,
    )
    with pytest.raises(StepUpRequiredError) as exc_info:
        await guard.authorize_privileged_operation(
            caller=caller,
            target_org_id="org_alpha",
            action=PrivilegedAction.ROTATE_API_KEY,
        )
    assert exc_info.value.required_nonce is not None
    assert exc_info.value.required_nonce.startswith("wp_nonce_")


@pytest.mark.asyncio
async def test_critical_risk_requires_four_eyes_and_step_up(test_db: DatabaseEngine):
    guard = PrivilegedSurfaceGuard(test_db)

    caller = PrivilegedCallerContext(
        principal_id="admin_requester",
        org_id="org_alpha",
        role=Role.ADMIN,
    )

    # 1. First fails because step-up is required
    with pytest.raises(StepUpRequiredError) as exc_info:
        await guard.authorize_privileged_operation(
            caller=caller,
            target_org_id="org_alpha",
            action=PrivilegedAction.UPDATE_SSO_IDP_CONFIG,
        )
    nonce = exc_info.value.required_nonce

    # Create step-up proof
    from datetime import UTC, datetime
    now_iso = datetime.now(UTC).isoformat()
    proof = StepUpProof(
        nonce=nonce,
        method=StepUpMethod.MFA_TOTP,
        auth_time=now_iso,
        token_or_code="123456",
    )

    # 2. Fails because Four-Eyes is required
    with pytest.raises(FourEyesRequiredError):
        await guard.authorize_privileged_operation(
            caller=caller,
            target_org_id="org_alpha",
            action=PrivilegedAction.UPDATE_SSO_IDP_CONFIG,
            step_up_proof=proof,
        )
