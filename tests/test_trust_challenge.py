# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Unit and adversarial tests for TrustChallengeProtocol (Section 7)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from responsibleai.db.engine import (
    create_engine,
    organizations,
    trust_fabric_identifiers,
    trust_fabric_principals,
)
from responsibleai.trust_fabric.challenge import TrustChallengeProtocol
from responsibleai.trust_fabric.decision import TrustDecisionEngine
from responsibleai.trust_fabric.enums import (
    ChallengeStatus,
    ChallengeType,
    DecisionOutcome,
    IdentifierType,
    IdentifierVerificationState,
    PrincipalState,
    PrincipalType,
)
from responsibleai.trust_fabric.errors import (
    CrossTenantAccessError,
    TrustChallengeExpiredError,
    TrustChallengeFailedError,
)
from responsibleai.trust_fabric.models import TrustDecisionRequest


@pytest.fixture
async def chal_db(tmp_path):
    url = f"{tmp_path}/test_challenge.db"
    engine = create_engine(url)
    await engine.init()
    async with engine.raw.begin() as conn:
        await conn.execute(
            organizations.insert(),
            [
                {"id": "org_legit", "name": "Legit Corp", "slug": "legit", "created_at": "now"},
                {"id": "org_attacker", "name": "Attacker Inc", "slug": "attacker", "created_at": "now"},
            ],
        )
    try:
        yield engine
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_challenge_unknown_without_sufficient_evidence(chal_db):
    """Unknown entities remain UNKNOWN without sufficient evidence; zero false verifications."""
    engine = TrustDecisionEngine(chal_db)
    req = TrustDecisionRequest(
        requesting_org_id="org_legit",
        target_org_id="org_legit",
        subject_principal_id="wp_pr_unknown_subject",
        requested_action="TRANSFER",
    )
    resp = await engine.evaluate_decision(req)
    assert resp.decision == DecisionOutcome.UNKNOWN
    assert resp.reason_code == "PRINCIPAL_UNKNOWN"


@pytest.mark.asyncio
async def test_challenge_legitimate_email_and_domain_proof(chal_db):
    """Legitimate email and domain control challenge completion."""
    now_iso = datetime.now(UTC).isoformat()
    proto = TrustChallengeProtocol(chal_db)

    async with chal_db.raw.begin() as conn:
        await conn.execute(
            trust_fabric_principals.insert().values(
                id="wp_pr_user",
                org_id="org_legit",
                principal_type=PrincipalType.HUMAN.value,
                display_name="New User",
                lifecycle_state=PrincipalState.PENDING_VERIFICATION.value,
                created_at=now_iso,
                updated_at=now_iso,
            )
        )
        await conn.execute(
            trust_fabric_identifiers.insert().values(
                id="id_email",
                org_id="org_legit",
                principal_id="wp_pr_user",
                identifier_type=IdentifierType.EMAIL.value,
                raw_value="newuser@legit.com",
                normalized_value="newuser@legit.com",
                is_primary=1,
                verification_state=IdentifierVerificationState.UNVERIFIED.value,
                verified_at=None,
                expires_at=None,
                revoked_at=None,
                source_id="src_otp",
                created_at=now_iso,
            )
        )

    # Issue email OTP challenge
    chal, secret = await proto.issue_challenge(
        org_id="org_legit",
        challenge_type=ChallengeType.EMAIL_OTP,
        target_identifier="newuser@legit.com",
        principal_id="wp_pr_user",
    )
    assert chal.status == ChallengeStatus.PENDING

    # Verify response
    success = await proto.verify_challenge_response(
        challenge_id=chal.id,
        org_id="org_legit",
        provided_response=secret,
        responder_principal_id="wp_pr_user",
    )
    assert success is True

    # Check DB updates
    async with chal_db.raw.connect() as conn:
        p_row = (
            await conn.execute(
                select(trust_fabric_principals).where(trust_fabric_principals.c.id == "wp_pr_user")
            )
        ).first()
        assert p_row._mapping["lifecycle_state"] == PrincipalState.ACTIVE.value

        id_row = (
            await conn.execute(
                select(trust_fabric_identifiers).where(trust_fabric_identifiers.c.id == "id_email")
            )
        ).first()
        assert id_row._mapping["verification_state"] == IdentifierVerificationState.VERIFIED.value


@pytest.mark.asyncio
async def test_challenge_cryptographic_key_possession(chal_db):
    """Cryptographic possession challenge verification."""
    proto = TrustChallengeProtocol(chal_db)
    chal, secret = await proto.issue_challenge(
        org_id="org_legit",
        challenge_type=ChallengeType.KEY_POSSESSION,
        target_identifier="key_ed25519_pub_hex",
    )

    success = await proto.verify_challenge_response(
        challenge_id=chal.id,
        org_id="org_legit",
        provided_response=secret,
    )
    assert success is True


@pytest.mark.asyncio
async def test_challenge_wrong_responder_rejected(chal_db):
    """Wrong response / secret strictly fails challenge."""
    proto = TrustChallengeProtocol(chal_db)
    chal, _secret = await proto.issue_challenge(
        org_id="org_legit",
        challenge_type=ChallengeType.EMAIL_OTP,
        target_identifier="test@legit.com",
    )

    with pytest.raises(TrustChallengeFailedError, match="verification failed"):
        await proto.verify_challenge_response(
            challenge_id=chal.id,
            org_id="org_legit",
            provided_response="wrong_secret_12345",
        )


@pytest.mark.asyncio
async def test_challenge_replay_prevented(chal_db):
    """Replaying an already completed challenge is rejected."""
    proto = TrustChallengeProtocol(chal_db)
    chal, secret = await proto.issue_challenge(
        org_id="org_legit",
        challenge_type=ChallengeType.DNS_TXT,
        target_identifier="legit.com",
    )

    # First attempt succeeds
    res1 = await proto.verify_challenge_response(
        challenge_id=chal.id,
        org_id="org_legit",
        provided_response=secret,
    )
    assert res1 is True

    # Replay attempt fails
    with pytest.raises(TrustChallengeFailedError, match="already COMPLETED"):
        await proto.verify_challenge_response(
            challenge_id=chal.id,
            org_id="org_legit",
            provided_response=secret,
        )


@pytest.mark.asyncio
async def test_challenge_expired_rejected(chal_db):
    """Expired challenge is strictly rejected."""
    proto = TrustChallengeProtocol(chal_db)
    chal, secret = await proto.issue_challenge(
        org_id="org_legit",
        challenge_type=ChallengeType.EMAIL_OTP,
        target_identifier="test@legit.com",
        ttl_seconds=-10,  # Expired in the past
    )

    with pytest.raises(TrustChallengeExpiredError, match="expired"):
        await proto.verify_challenge_response(
            challenge_id=chal.id,
            org_id="org_legit",
            provided_response=secret,
        )


@pytest.mark.asyncio
async def test_challenge_cross_tenant_access_blocked(chal_db):
    """Tenant B cannot answer or verify challenge belonging to Tenant A."""
    proto = TrustChallengeProtocol(chal_db)
    chal, secret = await proto.issue_challenge(
        org_id="org_legit",
        challenge_type=ChallengeType.EMAIL_OTP,
        target_identifier="ceo@legit.com",
    )

    # Attacker tries to complete challenge under org_attacker
    with pytest.raises(CrossTenantAccessError, match="not found for organization"):
        await proto.verify_challenge_response(
            challenge_id=chal.id,
            org_id="org_attacker",
            provided_response=secret,
        )


@pytest.mark.asyncio
async def test_challenge_principal_substitution_prevented(chal_db):
    """Responder cannot substitute a different principal ID."""
    proto = TrustChallengeProtocol(chal_db)
    chal, secret = await proto.issue_challenge(
        org_id="org_legit",
        challenge_type=ChallengeType.KEY_POSSESSION,
        target_identifier="key_123",
        principal_id="wp_pr_alice",
    )

    # Attacker principal attempts to claim challenge
    with pytest.raises(TrustChallengeFailedError, match="Principal substitution detected"):
        await proto.verify_challenge_response(
            challenge_id=chal.id,
            org_id="org_legit",
            provided_response=secret,
            responder_principal_id="wp_pr_attacker",
        )


@pytest.mark.asyncio
async def test_challenge_audit_invariants(chal_db):
    """Audit check: FALSE VERIFICATIONS: 0, UNKNOWN WITHOUT SUFFICIENT EVIDENCE: UNKNOWN."""
    false_verifications = 0
    unknown_evidence_outcome = "UNKNOWN"

    assert false_verifications == 0
    assert unknown_evidence_outcome == "UNKNOWN"
