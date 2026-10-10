# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Unit and Adversarial Tests for Step-Up Reauthentication & Nonce Security."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import insert

from responsibleai.auth import mfa
from responsibleai.db.engine import create_engine, org_api_keys, organizations
from responsibleai.iam.enums import PrivilegeRiskTier, StepUpMethod
from responsibleai.iam.errors import (
    StepUpVerificationFailedError,
)
from responsibleai.iam.models import StepUpProof
from responsibleai.iam.step_up import StepUpVerifier


@pytest.fixture
async def test_db():
    engine = create_engine(":memory:")
    await engine.init()
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id="org_stepup",
                name="StepUp Corp",
                slug="stepup-corp",
                monthly_budget_usd=10000.0,
                created_at="2026-09-12T00:00:00Z",
                plan="ENTERPRISE",
            )
        )
        # Add user with enrolled MFA secret
        secret = mfa.generate_secret()
        await conn.execute(
            insert(org_api_keys).values(
                id="user_mfa",
                org_id="org_stepup",
                name="user-mfa",
                role="ADMIN",
                key_hash="hash_mfa",
                created_at="2026-09-12T00:00:00Z",
                revoked=0,
                mfa_enrolled=1,
                mfa_secret=secret,
            )
        )
    yield engine, secret
    await engine.close()


@pytest.mark.asyncio
async def test_step_up_nonce_generation_and_consumption(test_db):
    engine, secret = test_db
    verifier = StepUpVerifier(engine)

    nonce = await verifier.issue_step_up_nonce(
        org_id="org_stepup",
        principal_id="user_mfa",
        action="ROTATE_API_KEY",
        ttl_seconds=300,
    )

    import pyotp

    code = pyotp.TOTP(secret).now()
    now_iso = datetime.now(UTC).isoformat()

    proof = StepUpProof(
        nonce=nonce,
        method=StepUpMethod.MFA_TOTP,
        auth_time=now_iso,
        token_or_code=code,
    )

    ok = await verifier.verify_and_consume_step_up(
        org_id="org_stepup",
        principal_id="user_mfa",
        action="ROTATE_API_KEY",
        risk_tier=PrivilegeRiskTier.PRIVILEGED_HIGH,
        proof=proof,
    )
    assert ok is True

    # Test Replay Defense: Second consumption with same nonce must fail!
    with pytest.raises(StepUpVerificationFailedError, match="already been consumed"):
        await verifier.verify_and_consume_step_up(
            org_id="org_stepup",
            principal_id="user_mfa",
            action="ROTATE_API_KEY",
            risk_tier=PrivilegeRiskTier.PRIVILEGED_HIGH,
            proof=proof,
        )


@pytest.mark.asyncio
async def test_step_up_action_binding_mismatch(test_db):
    engine, secret = test_db
    verifier = StepUpVerifier(engine)

    # Issued for ROTATE_API_KEY
    nonce = await verifier.issue_step_up_nonce(
        org_id="org_stepup",
        principal_id="user_mfa",
        action="ROTATE_API_KEY",
    )

    import pyotp

    code = pyotp.TOTP(secret).now()
    now_iso = datetime.now(UTC).isoformat()
    proof = StepUpProof(
        nonce=nonce,
        method=StepUpMethod.MFA_TOTP,
        auth_time=now_iso,
        token_or_code=code,
    )

    # Presented for DESTROY_TENANT
    with pytest.raises(StepUpVerificationFailedError, match="action mismatch"):
        await verifier.verify_and_consume_step_up(
            org_id="org_stepup",
            principal_id="user_mfa",
            action="DESTROY_TENANT",
            risk_tier=PrivilegeRiskTier.PRIVILEGED_CRITICAL,
            proof=proof,
        )


@pytest.mark.asyncio
async def test_step_up_stale_challenge_rejected(test_db):
    """Freshness is the age of the server-issued challenge; a client auth_time cannot extend it."""
    from sqlalchemy import update

    from responsibleai.db.engine import iam_step_up_nonces

    engine, secret = test_db
    verifier = StepUpVerifier(engine)

    nonce = await verifier.issue_step_up_nonce(
        org_id="org_stepup",
        principal_id="user_mfa",
        action="ROTATE_API_KEY",
    )
    # Challenge issued 20 minutes ago (exceeds the 15 minute window for HIGH).
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(iam_step_up_nonces).values(
                created_at=(datetime.now(UTC) - timedelta(minutes=20)).isoformat()
            )
        )
    import pyotp

    proof = StepUpProof(
        nonce=nonce,
        method=StepUpMethod.MFA_TOTP,
        auth_time=datetime.now(UTC).isoformat(),
        token_or_code=pyotp.TOTP(secret).now(),
    )

    with pytest.raises(StepUpVerificationFailedError, match="older than 900s"):
        await verifier.verify_and_consume_step_up(
            org_id="org_stepup",
            principal_id="user_mfa",
            action="ROTATE_API_KEY",
            risk_tier=PrivilegeRiskTier.PRIVILEGED_HIGH,
            proof=proof,
        )
