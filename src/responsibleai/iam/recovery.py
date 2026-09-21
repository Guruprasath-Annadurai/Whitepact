# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Sovereign Root Recovery & N-of-M Guardian Ceremony Service."""

from __future__ import annotations

import base64
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519
from sqlalchemy import and_, insert, select, update

from responsibleai.db.engine import (
    DatabaseEngine,
    iam_recovery_challenges,
    iam_recovery_policies,
    trust_fabric_trust_roots,
)
from responsibleai.db.revocation_epoch_repository import bump_epoch_on_connection
from responsibleai.iam.errors import (
    SovereignRecoveryError,
)
from responsibleai.iam.models import SovereignRecoveryPolicy, canonical_hash
from responsibleai.iam.session import SessionService


class SovereignRecoveryService:
    """Customer-controlled sovereign root recovery via cryptographic N-of-M guardian threshold."""

    def __init__(self, db: DatabaseEngine) -> None:
        self.db = db
        self.session_service = SessionService(db)

    async def register_recovery_policy(
        self,
        *,
        org_id: str,
        threshold: int,
        guardians: list[dict[str, str]],  # [{"name": "...", "public_key": "base64..."}]
    ) -> SovereignRecoveryPolicy:
        """Register customer guardian public keys and threshold for sovereign root recovery."""
        if threshold < 2:
            raise ValueError("Threshold must be at least 2 guardians.")
        if len(guardians) < threshold:
            raise ValueError(
                f"Guardian count ({len(guardians)}) cannot be less than threshold ({threshold})."
            )

        # Invariant: Guardian public keys must be strictly unique (anti-inflation attack)
        pub_keys = [g["public_key"] for g in guardians]
        if len(set(pub_keys)) != len(pub_keys):
            raise ValueError("Guardian public keys must be unique.")

        # Invariant: Platform operators cannot be registered as customer sovereign guardians
        for g in guardians:
            if g.get("is_platform_operator") or "operator" in g.get("name", "").lower():
                raise SovereignRecoveryError(
                    "Platform operators cannot be registered as customer guardians."
                )

        policy_id = f"rec_pol_{uuid.uuid4().hex}"
        now = datetime.now(UTC).isoformat()

        async with self.db.raw.begin() as conn:
            # Deactivate any existing active policy
            await conn.execute(
                update(iam_recovery_policies)
                .where(iam_recovery_policies.c.org_id == org_id)
                .values(active=0)
            )

            await conn.execute(
                insert(iam_recovery_policies).values(
                    id=policy_id,
                    org_id=org_id,
                    threshold=threshold,
                    guardians_json=json.dumps(guardians),
                    created_at=now,
                    active=1,
                )
            )

        return SovereignRecoveryPolicy(
            id=policy_id,
            org_id=org_id,
            threshold=threshold,
            guardians=guardians,
            created_at=now,
            active=True,
        )

    async def initiate_recovery_challenge(
        self,
        *,
        org_id: str,
        new_root_principal_id: str,
        new_root_public_key: str,
        ttl_seconds: int = 1800,  # 30 minutes
    ) -> str:
        """Initiate root recovery challenge, returning the challenge string to be signed by guardians."""
        challenge_id = f"rec_chal_{uuid.uuid4().hex}"
        nonce = secrets.token_urlsafe(32)
        now = datetime.now(UTC)
        expires_at = (now + timedelta(seconds=ttl_seconds)).isoformat()

        async with self.db.raw.begin() as conn:
            # Verify active policy exists
            pol_stmt = select(iam_recovery_policies).where(
                and_(
                    iam_recovery_policies.c.org_id == org_id,
                    iam_recovery_policies.c.active == 1,
                )
            )
            pol_row = (await conn.execute(pol_stmt)).first()
            if not pol_row:
                raise SovereignRecoveryError(
                    f"No active recovery policy registered for tenant {org_id!r}."
                )

            payload = {
                "challenge_id": challenge_id,
                "org_id": org_id,
                "nonce": nonce,
                "new_root_principal_id": new_root_principal_id,
                "new_root_public_key": new_root_public_key,
                "policy_id": pol_row.id,
                "issued_at": now.isoformat(),
            }
            challenge_message = canonical_hash(payload)

            await conn.execute(
                insert(iam_recovery_challenges).values(
                    id=challenge_id,
                    org_id=org_id,
                    new_root_principal_id=new_root_principal_id,
                    new_root_public_key=new_root_public_key,
                    challenge_message=challenge_message,
                    status="PENDING",
                    signatures_json="{}",
                    created_at=now.isoformat(),
                    expires_at=expires_at,
                    completed_at=None,
                )
            )

        return challenge_message

    async def submit_guardian_signature(
        self,
        *,
        org_id: str,
        challenge_message: str,
        guardian_name: str,
        signature_b64: str,
    ) -> int:
        """Submit a partial guardian signature against the challenge message."""
        now = datetime.now(UTC).isoformat()

        async with self.db.raw.begin() as conn:
            # 1. Fetch challenge
            chal_stmt = select(iam_recovery_challenges).where(
                and_(
                    iam_recovery_challenges.c.org_id == org_id,
                    iam_recovery_challenges.c.challenge_message == challenge_message,
                )
            )
            chal_row = (await conn.execute(chal_stmt)).first()
            if not chal_row:
                raise SovereignRecoveryError("Recovery challenge not found.")

            chal = dict(chal_row._mapping)
            if chal["status"] != "PENDING" or now >= chal["expires_at"]:
                raise SovereignRecoveryError("Challenge is not active or has expired.")

            # 2. Fetch active policy
            pol_stmt = select(iam_recovery_policies).where(
                and_(
                    iam_recovery_policies.c.org_id == org_id,
                    iam_recovery_policies.c.active == 1,
                )
            )
            pol = dict((await conn.execute(pol_stmt)).one()._mapping)
            if pol["created_at"] > chal["created_at"]:
                raise SovereignRecoveryError(
                    "Active recovery policy was modified after challenge initiation."
                )
            guardians = json.loads(pol["guardians_json"])

            # Find matching guardian public key
            guardian = next((g for g in guardians if g["name"] == guardian_name), None)
            if not guardian:
                raise SovereignRecoveryError(f"Guardian {guardian_name!r} not in active policy.")

            # 3. Cryptographically verify signature
            pub_bytes = base64.b64decode(guardian["public_key"])
            sig_bytes = base64.b64decode(signature_b64)
            verifier = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
            try:
                verifier.verify(sig_bytes, challenge_message.encode("utf-8"))
            except InvalidSignature as exc:
                raise SovereignRecoveryError(
                    f"Invalid signature from guardian {guardian_name!r}."
                ) from exc

            # 4. Record signature
            signatures = json.loads(chal["signatures_json"])
            signatures[guardian_name] = signature_b64

            await conn.execute(
                update(iam_recovery_challenges)
                .where(iam_recovery_challenges.c.id == chal["id"])
                .values(signatures_json=json.dumps(signatures))
            )

            return len(signatures)

    async def finalize_sovereign_recovery(
        self,
        *,
        org_id: str,
        challenge_message: str,
    ) -> bool:
        """Execute atomic root recovery once guardian threshold is reached."""
        now = datetime.now(UTC).isoformat()

        async with self.db.raw.begin() as conn:
            # 1. Fetch challenge & policy
            chal_stmt = select(iam_recovery_challenges).where(
                and_(
                    iam_recovery_challenges.c.org_id == org_id,
                    iam_recovery_challenges.c.challenge_message == challenge_message,
                )
            )
            chal = dict((await conn.execute(chal_stmt)).one()._mapping)
            pol_stmt = select(iam_recovery_policies).where(
                and_(
                    iam_recovery_policies.c.org_id == org_id,
                    iam_recovery_policies.c.active == 1,
                )
            )
            pol = dict((await conn.execute(pol_stmt)).one()._mapping)
            if pol["created_at"] > chal["created_at"]:
                raise SovereignRecoveryError(
                    "Active recovery policy was modified after challenge initiation."
                )

            signatures = json.loads(chal["signatures_json"])
            threshold = pol["threshold"]

            if len(signatures) < threshold:
                raise SovereignRecoveryError(
                    f"Threshold not met: required {threshold}, collected {len(signatures)}."
                )

            # 2. Identify old root principal and root record
            old_root_stmt = select(trust_fabric_trust_roots).where(
                and_(
                    trust_fabric_trust_roots.c.org_id == org_id,
                    trust_fabric_trust_roots.c.status == "ACTIVE",
                )
            )
            old_root_row = (await conn.execute(old_root_stmt)).first()
            old_root_principal_id = old_root_row.root_principal_id if old_root_row else None

            # 3. Atomically update or insert root in trust_fabric_trust_roots
            from responsibleai.trust_fabric.models import compute_digest

            if old_root_row:
                new_root_id = old_root_row.id
                payload = {
                    "id": new_root_id,
                    "org_id": org_id,
                    "root_principal_id": chal["new_root_principal_id"],
                    "root_public_key": chal["new_root_public_key"],
                    "established_at": now,
                    "key_algorithm": "Ed25519",
                }
                canonical_digest = compute_digest(payload)
                await conn.execute(
                    update(trust_fabric_trust_roots)
                    .where(trust_fabric_trust_roots.c.id == old_root_row.id)
                    .values(
                        root_principal_id=chal["new_root_principal_id"],
                        root_public_key=chal["new_root_public_key"],
                        key_algorithm="Ed25519",
                        established_at=now,
                        status="ACTIVE",
                        canonical_digest=canonical_digest,
                    )
                )
            else:
                new_root_id = f"wp_root_{uuid.uuid4().hex}"
                payload = {
                    "id": new_root_id,
                    "org_id": org_id,
                    "root_principal_id": chal["new_root_principal_id"],
                    "root_public_key": chal["new_root_public_key"],
                    "established_at": now,
                    "key_algorithm": "Ed25519",
                }
                canonical_digest = compute_digest(payload)
                await conn.execute(
                    insert(trust_fabric_trust_roots).values(
                        id=new_root_id,
                        org_id=org_id,
                        root_principal_id=chal["new_root_principal_id"],
                        root_public_key=chal["new_root_public_key"],
                        key_algorithm="Ed25519",
                        established_at=now,
                        status="ACTIVE",
                        canonical_digest=canonical_digest,
                    )
                )

            # 4. Mark challenge completed
            await conn.execute(
                update(iam_recovery_challenges)
                .where(iam_recovery_challenges.c.id == chal["id"])
                .values(status="COMPLETED", completed_at=now)
            )

            # 5. Bump tenant revocation epoch
            await bump_epoch_on_connection(conn, org_id, scope="iam_session")
            await bump_epoch_on_connection(conn, org_id, scope="governance")

        # 6. Revoke all active sessions for old root principal
        if old_root_principal_id:
            await self.session_service.revoke_all_principal_sessions(
                org_id=org_id, principal_id=old_root_principal_id
            )

        return True
