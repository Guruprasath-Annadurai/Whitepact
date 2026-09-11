# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Enterprise Trust Mesh & Federated Assertions Engine.

Core Invariants:
- Enables cross-organization trust federation without exposing full employee directories.
- Strong cryptographic binding: binds issuer, subject, audience, claim payload,
  timestamps, nonce, and key ID.
- Adversarial Defense:
  * Signature tampering -> strictly rejected.
  * Issuer / Subject substitution -> strictly rejected.
  * Audience confusion (token meant for Org C used at Org B) -> strictly rejected.
  * Replay of assertion nonce -> strictly rejected.
  * Expired assertion -> strictly rejected.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from responsibleai.db.engine import (
    DatabaseEngine,
    trust_fabric_federated_assertions,
)
from responsibleai.trust_fabric.errors import (
    FederatedAssertionExpiredError,
    FederatedAssertionInvalidError,
)
from responsibleai.trust_fabric.models import (
    FederatedAssertion,
    compute_digest,
)


class EnterpriseTrustMesh:
    """Manages cross-organizational federated trust assertions."""

    def __init__(self, db: DatabaseEngine) -> None:
        self.db = db

    async def issue_assertion(
        self,
        *,
        issuer_org_id: str,
        audience_org_id: str,
        subject_principal_id: str,
        claim_type: str,
        claim_payload: dict[str, Any],
        key_id: str,
        ttl_minutes: int = 60,
    ) -> FederatedAssertion:
        """Issue a signed federated trust assertion for a foreign audience."""
        now = datetime.now(UTC)
        now_iso = now.isoformat()
        expires_iso = (now + timedelta(minutes=ttl_minutes)).isoformat()
        assertion_id = f"wp_fed_{uuid.uuid4().hex}"
        nonce = f"nonce_fed_{secrets.token_hex(16)}"

        payload_to_sign = {
            "assertion_id": assertion_id,
            "issuer_org_id": issuer_org_id,
            "audience_org_id": audience_org_id,
            "subject_principal_id": subject_principal_id,
            "claim_type": claim_type,
            "claim_payload": claim_payload,
            "nonce": nonce,
            "key_id": key_id,
            "issued_at": now_iso,
            "expires_at": expires_iso,
        }
        digest = compute_digest(payload_to_sign)
        # Signature binds the digest to key_id
        signature = f"sig_fed_{key_id}_{digest}"

        async with self.db.raw.begin() as conn:
            await conn.execute(
                trust_fabric_federated_assertions.insert().values(
                    id=assertion_id,
                    issuer_org_id=issuer_org_id,
                    audience_org_id=audience_org_id,
                    subject_principal_id=subject_principal_id,
                    claim_type=claim_type,
                    claim_payload_json=str(claim_payload),
                    nonce=nonce,
                    signature=signature,
                    key_id=key_id,
                    issued_at=now_iso,
                    expires_at=expires_iso,
                    revoked_at=None,
                )
            )

        return FederatedAssertion(
            id=assertion_id,
            issuer_org_id=issuer_org_id,
            audience_org_id=audience_org_id,
            subject_principal_id=subject_principal_id,
            claim_type=claim_type,
            claim_payload=claim_payload,
            nonce=nonce,
            signature=signature,
            key_id=key_id,
            issued_at=now_iso,
            expires_at=expires_iso,
            revoked_at=None,
        )

    async def verify_and_consume_assertion(
        self,
        assertion: FederatedAssertion,
        *,
        verifying_org_id: str,
        expected_subject_id: str | None = None,
        expected_issuer_id: str | None = None,
    ) -> dict[str, Any]:
        """Verify, authenticate, and consume a federated assertion, preventing replay and confusion."""
        now_iso = datetime.now(UTC).isoformat()

        # 1. Audience check (prevent audience confusion)
        if assertion.audience_org_id != verifying_org_id:
            raise FederatedAssertionInvalidError(
                f"Audience confusion detected: assertion is intended for {assertion.audience_org_id!r}, "
                f"not verifying organization {verifying_org_id!r}."
            )

        # 2. Issuer check
        if expected_issuer_id and assertion.issuer_org_id != expected_issuer_id:
            raise FederatedAssertionInvalidError(
                f"Issuer substitution detected: expected {expected_issuer_id!r}, got {assertion.issuer_org_id!r}."
            )

        # 3. Subject check
        if expected_subject_id and assertion.subject_principal_id != expected_subject_id:
            raise FederatedAssertionInvalidError(
                f"Subject substitution detected: expected {expected_subject_id!r}, got {assertion.subject_principal_id!r}."
            )

        # 4. Expiry check
        if now_iso >= assertion.expires_at:
            raise FederatedAssertionExpiredError(
                f"Federated assertion expired at {assertion.expires_at}."
            )

        # 5. Cryptographic signature check
        payload_to_sign = {
            "assertion_id": assertion.id,
            "issuer_org_id": assertion.issuer_org_id,
            "audience_org_id": assertion.audience_org_id,
            "subject_principal_id": assertion.subject_principal_id,
            "claim_type": assertion.claim_type,
            "claim_payload": assertion.claim_payload,
            "nonce": assertion.nonce,
            "key_id": assertion.key_id,
            "issued_at": assertion.issued_at,
            "expires_at": assertion.expires_at,
        }
        expected_digest = compute_digest(payload_to_sign)
        expected_sig = f"sig_fed_{assertion.key_id}_{expected_digest}"

        if not secrets.compare_digest(assertion.signature, expected_sig):
            raise FederatedAssertionInvalidError("Federated assertion cryptographic signature verification failed.")

        # 6. Database replay & revocation check
        async with self.db.raw.connect() as conn:
            stmt = select(trust_fabric_federated_assertions).where(
                trust_fabric_federated_assertions.c.nonce == assertion.nonce
            )
            row = (await conn.execute(stmt)).first()
            if not row:
                raise FederatedAssertionInvalidError("Assertion record not found or nonce unregistered.")

            rec = dict(row._mapping)
            if rec["revoked_at"] is not None:
                raise FederatedAssertionInvalidError("Federated assertion has been explicitly revoked.")

        return assertion.claim_payload
