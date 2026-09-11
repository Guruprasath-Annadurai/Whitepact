# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Trust Challenge Protocol & Unknown Handling.

Constitutional Invariants:
- Zero Hallucination: An unknown or unverified principal is explicitly valued
  as UNKNOWN. WhitePact never fabricates identity, affiliations, or authority.
- Trust Challenge: Offers verifiable mechanisms (DNS TXT, Key Possession, Email OTP,
  Org Assertion) to establish identity legitimacy.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, select, update

from responsibleai.db.engine import (
    DatabaseEngine,
    trust_fabric_challenges,
    trust_fabric_identifiers,
    trust_fabric_principals,
)
from responsibleai.trust_fabric.enums import (
    ChallengeStatus,
    ChallengeType,
    IdentifierVerificationState,
    PrincipalState,
)
from responsibleai.trust_fabric.errors import (
    CrossTenantAccessError,
    TrustChallengeExpiredError,
    TrustChallengeFailedError,
)
from responsibleai.trust_fabric.models import (
    TrustChallenge,
)


class TrustChallengeProtocol:
    """Issues and verifies trust challenges to establish evidence-backed legitimacy."""

    def __init__(self, db: DatabaseEngine) -> None:
        self.db = db

    async def issue_challenge(
        self,
        *,
        org_id: str,
        challenge_type: ChallengeType,
        target_identifier: str,
        principal_id: str | None = None,
        ttl_seconds: int = 300,
    ) -> tuple[TrustChallenge, str]:
        """Issue a challenge to prove control over an identifier or key."""
        challenge_id = f"wp_chal_{uuid.uuid4().hex}"
        nonce = f"wp_chnonce_{secrets.token_hex(16)}"
        secret_secret = secrets.token_urlsafe(16)
        expected_hash = hashlib.sha256(f"{nonce}:{secret_secret}".encode()).hexdigest()

        now = datetime.now(UTC)
        now_iso = now.isoformat()
        expires_iso = (now + timedelta(seconds=ttl_seconds)).isoformat()

        async with self.db.raw.begin() as conn:
            await conn.execute(
                trust_fabric_challenges.insert().values(
                    id=challenge_id,
                    principal_id=principal_id,
                    org_id=org_id,
                    challenge_type=challenge_type.value,
                    target_identifier=target_identifier,
                    nonce=nonce,
                    expected_response_hash=expected_hash,
                    status=ChallengeStatus.PENDING.value,
                    issued_at=now_iso,
                    expires_at=expires_iso,
                    completed_at=None,
                )
            )

        challenge = TrustChallenge(
            id=challenge_id,
            org_id=org_id,
            principal_id=principal_id,
            challenge_type=challenge_type,
            target_identifier=target_identifier,
            nonce=nonce,
            expected_response_hash=expected_hash,
            status=ChallengeStatus.PENDING,
            issued_at=now_iso,
            expires_at=expires_iso,
            completed_at=None,
        )

        return challenge, secret_secret

    async def verify_challenge_response(
        self,
        *,
        challenge_id: str,
        org_id: str,
        provided_response: str,
    ) -> bool:
        """Verify the response to an issued trust challenge."""
        now_iso = datetime.now(UTC).isoformat()

        async with self.db.raw.connect() as conn:
            stmt = select(trust_fabric_challenges).where(
                and_(
                    trust_fabric_challenges.c.id == challenge_id,
                    trust_fabric_challenges.c.org_id == org_id,
                )
            )
            row = (await conn.execute(stmt)).first()
            if not row:
                raise CrossTenantAccessError(f"Challenge {challenge_id!r} not found for organization {org_id!r}.")

            data = dict(row._mapping)

        if data["status"] != ChallengeStatus.PENDING.value:
            raise TrustChallengeFailedError(f"Challenge is already {data['status']}.")

        if now_iso >= data["expires_at"]:
            async with self.db.raw.begin() as conn:
                await conn.execute(
                    update(trust_fabric_challenges)
                    .where(trust_fabric_challenges.c.id == challenge_id)
                    .values(status=ChallengeStatus.EXPIRED.value)
                )
            raise TrustChallengeExpiredError("Trust challenge has expired.")

        # Compute provided response hash
        provided_hash = hashlib.sha256(f"{data['nonce']}:{provided_response}".encode()).hexdigest()

        if not secrets.compare_digest(provided_hash, data["expected_response_hash"]):
            async with self.db.raw.begin() as conn:
                await conn.execute(
                    update(trust_fabric_challenges)
                    .where(trust_fabric_challenges.c.id == challenge_id)
                    .values(status=ChallengeStatus.FAILED.value)
                )
            raise TrustChallengeFailedError("Challenge response verification failed.")

        # Challenge passed: mark completed
        async with self.db.raw.begin() as conn:
            await conn.execute(
                update(trust_fabric_challenges)
                .where(trust_fabric_challenges.c.id == challenge_id)
                .values(
                    status=ChallengeStatus.COMPLETED.value,
                    completed_at=now_iso,
                )
            )
            # If bound to an identifier, advance identifier verification state
            await conn.execute(
                update(trust_fabric_identifiers)
                .where(
                    and_(
                        trust_fabric_identifiers.c.org_id == org_id,
                        trust_fabric_identifiers.c.normalized_value == data["target_identifier"],
                    )
                )
                .values(
                    verification_state=IdentifierVerificationState.VERIFIED.value,
                    verified_at=now_iso,
                )
            )
            # If principal was pending, advance to active
            if data["principal_id"]:
                await conn.execute(
                    update(trust_fabric_principals)
                    .where(
                        and_(
                            trust_fabric_principals.c.id == data["principal_id"],
                            trust_fabric_principals.c.lifecycle_state
                            == PrincipalState.PENDING_VERIFICATION.value,
                        )
                    )
                    .values(lifecycle_state=PrincipalState.ACTIVE.value)
                )

        return True
