# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Enterprise Customer Authority & Trust Fabric Bridge Service.

Constitutional Invariants:
1. Registration does NOT equal authority: An organization or agent signup never
   manufactures runtime execution authority.
2. Legitimate Customer Root: Authority originates exclusively from an authenticated,
   verified customer owner via a replay-resistant, atomic bootstrap ceremony.
3. Explicit Scoped Consent: The customer explicitly binds permitted action types,
   target resource patterns, and bounded purpose before any agent can act.
4. Single Authority Kernel: Bridges Trust Fabric root ownership into canonical
   governance root records (governance_root_authority_records & governance_consent_proofs)
   under a single shared revocation epoch.
5. Strict Multi-Tenant Isolation: Cross-tenant operations strictly fail closed.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, select, update

from responsibleai.db.delegation_repository import DelegationRepository
from responsibleai.db.engine import (
    DatabaseEngine,
    authority_containment_records,
    authority_recovery_requests,
    authority_recovery_votes,
    authority_step_up_challenges,
    governance_consent_proofs,
    governance_delegations,
    governance_root_authority_records,
    org_security_policies,
    organizations,
    passkey_credentials,
    trust_fabric_bootstrap_records,
    trust_fabric_principals,
    trust_fabric_trust_roots,
    web_memberships,
    web_sessions,
    web_users,
)
from responsibleai.db.revocation_epoch_repository import (
    RevocationEpochRepository,
    bump_epoch_on_connection,
    lock_epoch,
)
from responsibleai.enterprise.audit import EnterpriseAuditLog
from responsibleai.enterprise.authority.errors import (
    agent_not_found,
    already_voted,
    assurance_required,
    bootstrap_expired,
    bootstrap_invalid,
    bootstrap_replay,
    consent_invalid,
    containment_forbidden,
    containment_invalid_target,
    passkey_step_up_required,
    proof_of_possession_invalid,
    quorum_not_met,
    recovery_already_executed,
    recovery_digest_mismatch,
    recovery_expired,
    recovery_request_not_found,
    root_already_exists,
    root_not_found,
    self_approval_blocked,
    unauthorized_caller,
    webauthn_assertion_invalid,
    webauthn_challenge_expired,
    webauthn_challenge_replay,
)
from responsibleai.enterprise.errors import (
    BREAK_GLASS_DENIED,
    CROSS_TENANT,
    FORBIDDEN,
    WEBAUTHN_INVALID,
    forbidden,
)
from responsibleai.enterprise.security.rate_limit import DurableIdentityRateLimiter
from responsibleai.enterprise.security.webauthn import (
    b64url_decode,
    b64url_encode,
    parse_client_data,
    verify_assertion,
)
from responsibleai.enterprise.service import Actor
from responsibleai.governance.consent_proof import (
    ConsentMethod,
    build_consent_proof,
)
from responsibleai.governance.root_authority import (
    RootType,
    build_root_authority_record,
)
from responsibleai.rbac.models import Role
from responsibleai.trust_fabric.enums import PrincipalState, PrincipalType
from responsibleai.trust_fabric.models import compute_digest


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime | None = None) -> str:
    return (dt or _now()).isoformat()


def compute_canonical_operation_digest(action: str, params: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 digest of canonical action parameters."""
    canonical_dict: dict[str, Any] = {"action": action}
    for k, v in sorted(params.items()):
        if isinstance(v, list):
            canonical_dict[k] = sorted(str(x) for x in v)
        elif isinstance(v, dict):
            canonical_dict[k] = json.loads(json.dumps(v, sort_keys=True))
        else:
            canonical_dict[k] = str(v) if v is not None else ""
    raw = json.dumps(canonical_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def verify_root_proof_of_possession(
    org_id: str,
    nonce: str,
    token_hash: str,
    root_public_key: str,
    signature_b64: str,
) -> None:
    """Verify Ed25519 signature over ceremony parameters to prove possession of root key."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    try:
        # root_public_key may be hex or b64
        if len(root_public_key) == 64:
            pub_bytes = bytes.fromhex(root_public_key)
        else:
            pub_bytes = b64url_decode(root_public_key)

        sig_bytes = b64url_decode(signature_b64)
        message = f"WP_ROOT_POP:{org_id}:{nonce}:{token_hash}".encode("utf-8")

        pub = Ed25519PublicKey.from_public_bytes(pub_bytes)
        pub.verify(sig_bytes, message)
    except Exception as exc:
        raise proof_of_possession_invalid(f"Proof of possession verification failed: {exc}") from exc


class CustomerAuthorityService:
    """Manages legitimate customer root authority, consent, and agent delegation."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine
        self._audit = EnterpriseAuditLog(engine)
        self._delegations = DelegationRepository(engine)
        self._epochs = RevocationEpochRepository(engine)

    def _verify_tenant_and_role(self, actor: Actor, org_id: str, require_owner: bool = False) -> None:
        """Enforce authenticated tenant context and role authority."""
        if actor.org_id != org_id:
            raise forbidden(CROSS_TENANT, "Cross-tenant access strictly forbidden.")
        if require_owner:
            if actor.role != Role.OWNER:
                raise unauthorized_caller("This operation requires verified Organization Owner role.")
        else:
            if actor.role not in {Role.OWNER, Role.ADMIN}:
                raise unauthorized_caller("This operation requires Organization Owner or Admin role.")

    async def initiate_root_bootstrap(
        self,
        actor: Actor,
        *,
        org_id: str,
        ttl_seconds: int = 900,
        require_identity_assurance: bool = False,
        require_passkey_stepup: bool = False,
    ) -> dict[str, Any]:
        """Initiate a server-generated, replay-resistant bootstrap ceremony.

        Returns a one-time challenge token and nonce bound to the authenticated owner.
        """
        self._verify_tenant_and_role(actor, org_id, require_owner=True)

        if require_identity_assurance:
            async with self._engine.raw.connect() as conn:
                row = (
                    await conn.execute(
                        select(web_users.c.verification_status).where(web_users.c.id == actor.user_id)
                    )
                ).first()
                if not row or row[0] not in {"VERIFIED", "IDENTITY_VERIFIED", "BASIC_VERIFIED"}:
                    raise assurance_required()

        # Check if organization already possesses an active canonical root
        async with self._engine.raw.connect() as conn:
            canon_root = (
                await conn.execute(
                    select(governance_root_authority_records.c.root_id).where(
                        and_(
                            governance_root_authority_records.c.organization_id == org_id,
                            governance_root_authority_records.c.revoked_at.is_(None),
                        )
                    )
                )
            ).first()
            if canon_root:
                raise root_already_exists("Organization already has an active canonical root authority.")

            tf_root = (
                await conn.execute(
                    select(trust_fabric_trust_roots.c.id).where(
                        and_(
                            trust_fabric_trust_roots.c.org_id == org_id,
                            trust_fabric_trust_roots.c.status == "ACTIVE",
                        )
                    )
                )
            ).first()
            if tf_root:
                raise root_already_exists("Organization already has an active Trust Fabric root.")

        token = f"wp_boot_{secrets.token_urlsafe(32)}"
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        nonce = f"wp_nonce_{secrets.token_hex(16)}"
        now_dt = _now()
        expires_at_dt = now_dt + timedelta(seconds=ttl_seconds)
        expires_at = _iso(expires_at_dt)
        rec_id = f"wp_brec_{uuid.uuid4().hex}"

        async with self._engine.raw.begin() as conn:
            existing_rec = (
                await conn.execute(
                    select(trust_fabric_bootstrap_records).where(
                        trust_fabric_bootstrap_records.c.org_id == org_id
                    )
                )
            ).first()

            if existing_rec:
                row = dict(existing_rec._mapping)
                if row["consumed_at"] is not None:
                    # If previously consumed but root was revoked, allow refreshing ceremony
                    # check if active root still exists
                    has_root = (
                        await conn.execute(
                            select(governance_root_authority_records.c.root_id).where(
                                and_(
                                    governance_root_authority_records.c.organization_id == org_id,
                                    governance_root_authority_records.c.revoked_at.is_(None),
                                )
                            )
                        )
                    ).first()
                    if has_root:
                        raise root_already_exists()
                await conn.execute(
                    update(trust_fabric_bootstrap_records)
                    .where(trust_fabric_bootstrap_records.c.org_id == org_id)
                    .values(
                        token_hash=token_hash,
                        nonce=nonce,
                        expires_at=expires_at,
                        consumed_at=None,
                        claimed_by_principal_id=actor.user_id,
                        require_passkey_stepup=1 if require_passkey_stepup else 0,
                        created_at=_iso(now_dt),
                    )
                )
            else:
                await conn.execute(
                    trust_fabric_bootstrap_records.insert().values(
                        id=rec_id,
                        org_id=org_id,
                        token_hash=token_hash,
                        expires_at=expires_at,
                        consumed_at=None,
                        claimed_by_principal_id=actor.user_id,
                        nonce=nonce,
                        require_passkey_stepup=1 if require_passkey_stepup else 0,
                        created_at=_iso(now_dt),
                    )
                )

        return {
            "ceremony_id": rec_id,
            "organization_id": org_id,
            "token": token,
            "nonce": nonce,
            "expires_at": expires_at,
            "bound_owner_id": actor.user_id,
            "require_passkey_stepup": require_passkey_stepup,
        }

    async def create_authority_stepup_challenge(
        self,
        actor: Actor,
        *,
        org_id: str,
        action: str,
        operation_digest: str,
        ttl_seconds: int = 300,
    ) -> dict[str, Any]:
        """Issue a short-lived, replay-resistant WebAuthn challenge bound to tenant, user, action, and digest."""
        self._verify_tenant_and_role(actor, org_id)

        raw_challenge = secrets.token_bytes(32)
        challenge_b64 = b64url_encode(raw_challenge)
        challenge_hash = hashlib.sha256(challenge_b64.encode("utf-8")).hexdigest()

        rp_id = os.environ.get("WP_RP_ID", "localhost")
        origin = os.environ.get("WP_ORIGIN", "http://localhost:3000")
        now_dt = _now()
        expires_at_dt = now_dt + timedelta(seconds=ttl_seconds)
        expires_at = _iso(expires_at_dt)
        rec_id = f"wp_ch_{uuid.uuid4().hex}"

        async with self._engine.raw.begin() as conn:
            await conn.execute(
                authority_step_up_challenges.insert().values(
                    challenge_hash=challenge_hash,
                    user_id=actor.user_id,
                    org_id=org_id,
                    action=action,
                    operation_digest=operation_digest,
                    rp_id=rp_id,
                    origin=origin,
                    raw_challenge_b64=challenge_b64,
                    expires_at=expires_at,
                    consumed_at=None,
                    created_at=_iso(now_dt),
                )
            )

        return {
            "challenge_hash": challenge_hash,
            "challenge": challenge_b64,
            "rp_id": rp_id,
            "origin": origin,
            "action": action,
            "operation_digest": operation_digest,
            "expires_at": expires_at,
        }

    async def _verify_webauthn_stepup_on_conn(
        self,
        conn: Any,
        *,
        actor: Actor,
        org_id: str,
        action: str,
        operation_digest: str,
        assertion: dict[str, Any],
    ) -> dict[str, Any]:
        """Verify WebAuthn assertion against unconsumed challenge and active user passkey."""
        required_fields = ["credential_id", "client_data_json", "authenticator_data", "signature"]
        for f in required_fields:
            if f not in assertion:
                raise webauthn_assertion_invalid(f"Assertion missing required field: {f!r}")

        client_data_b64 = assertion["client_data_json"]
        auth_data_b64 = assertion["authenticator_data"]
        sig_b64 = assertion["signature"]
        credential_id = assertion["credential_id"]

        try:
            client_data = parse_client_data(client_data_b64)
        except Exception as exc:
            raise webauthn_assertion_invalid(f"Failed to parse clientDataJSON: {exc}") from exc

        challenge_b64 = b64url_encode(client_data.challenge)
        challenge_hash = hashlib.sha256(challenge_b64.encode("utf-8")).hexdigest()
        now_iso = _iso()

        # Look up challenge
        ch_row = (
            await conn.execute(
                select(authority_step_up_challenges).where(
                    and_(
                        authority_step_up_challenges.c.challenge_hash == challenge_hash,
                        authority_step_up_challenges.c.org_id == org_id,
                        authority_step_up_challenges.c.user_id == actor.user_id,
                    )
                )
            )
        ).first()

        if not ch_row:
            raise webauthn_assertion_invalid("No matching step-up challenge found for user, org, and challenge.")

        ch = dict(ch_row._mapping)
        if ch["action"] != action:
            raise webauthn_assertion_invalid(
                f"Step-up challenge was issued for action {ch['action']!r}, not {action!r}."
            )

        if ch["operation_digest"] != operation_digest:
            raise webauthn_assertion_invalid("Operation digest mismatch between challenge and ceremony.")

        if ch["consumed_at"] is not None:
            raise webauthn_challenge_replay("Step-up challenge has already been consumed.")

        if now_iso >= ch["expires_at"]:
            raise webauthn_challenge_expired(f"Step-up challenge expired at {ch['expires_at']}.")

        # Mark challenge consumed atomically
        await conn.execute(
            update(authority_step_up_challenges)
            .where(authority_step_up_challenges.c.challenge_hash == challenge_hash)
            .values(consumed_at=now_iso)
        )

        # Look up passkey credential
        cred_row = (
            await conn.execute(
                select(passkey_credentials).where(
                    and_(
                        passkey_credentials.c.credential_id == credential_id,
                        passkey_credentials.c.user_id == actor.user_id,
                        passkey_credentials.c.status == "ACTIVE",
                    )
                )
            )
        ).first()

        if not cred_row:
            raise webauthn_assertion_invalid(
                f"Active passkey credential {credential_id!r} not found for user {actor.user_id!r}."
            )

        cred = dict(cred_row._mapping)
        user_row = (
            await conn.execute(select(web_users).where(web_users.c.id == actor.user_id))
        ).first()
        if not user_row or user_row.disabled or user_row.verification_status == "SUSPENDED":
            raise unauthorized_caller("User account is disabled or suspended.")

        previous_sign_count = int(cred.get("sign_count") or 0)

        try:
            pub_key_bytes = b64url_decode(cred["public_key"])
            new_sign_count = verify_assertion(
                client_data_b64=client_data_b64,
                authenticator_data_b64=auth_data_b64,
                signature_b64=sig_b64,
                public_key_uncompressed=pub_key_bytes,
                expected_type="webauthn.get",
                expected_origin=ch["origin"],
                expected_rp_id=ch["rp_id"],
                expected_challenge=client_data.challenge,
                require_uv=True,
                previous_sign_count=previous_sign_count,
            )
        except Exception as exc:
            raise webauthn_assertion_invalid(f"WebAuthn assertion verification failed: {exc}") from exc

        # Advance sign count
        if new_sign_count == 0 and previous_sign_count == 0:
            await conn.execute(
                update(passkey_credentials)
                .where(passkey_credentials.c.id == cred["id"])
                .values(last_used_at=now_iso)
            )
        else:
            await conn.execute(
                update(passkey_credentials)
                .where(
                    and_(
                        passkey_credentials.c.id == cred["id"],
                        passkey_credentials.c.sign_count < new_sign_count,
                    )
                )
                .values(sign_count=new_sign_count, last_used_at=now_iso)
            )

        return {
            "credential_id": credential_id,
            "user_id": actor.user_id,
            "rp_id": ch["rp_id"],
            "sign_count": new_sign_count,
            "backup_eligible": cred.get("backup_eligible"),
            "backup_state": cred.get("backup_state"),
            "verified_at": now_iso,
        }

    async def complete_root_bootstrap(
        self,
        actor: Actor,
        *,
        org_id: str,
        token: str,
        nonce: str,
        root_public_key: str,
        scope_description: str,
        purpose: str,
        allowed_action_types: list[str],
        allowed_targets: list[str],
        key_algorithm: str = "Ed25519",
        consent_method: str = "CRYPTOGRAPHIC_CEREMONY",
        evidence_refs: list[str] | None = None,
        webauthn_assertion: dict[str, Any] | None = None,
        root_signature: str | None = None,
    ) -> dict[str, Any]:
        """Atomically complete root bootstrap ceremony with explicit scoped consent.

        Bridges Trust Fabric into canonical governance root authority and consent proofs.
        """
        self._verify_tenant_and_role(actor, org_id, require_owner=True)

        if not token or not nonce:
            raise bootstrap_invalid("Token and nonce are required.")
        if not scope_description or not scope_description.strip():
            raise consent_invalid("Scope description cannot be empty.")
        if not purpose or not purpose.strip():
            raise consent_invalid("Purpose cannot be empty.")
        if not allowed_action_types:
            raise consent_invalid("Allowed action types list cannot be empty.")
        if not allowed_targets:
            raise consent_invalid("Allowed targets list cannot be empty.")

        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        now_dt = _now()
        now_iso = _iso(now_dt)

        async with self._engine.raw.begin() as conn:
            # 1. Lock tenant revocation epoch to serialize concurrent ceremony attempts
            await lock_epoch(conn, org_id)

            # 2. Check no active canonical root already exists (anti-race)
            existing_canon = (
                await conn.execute(
                    select(governance_root_authority_records.c.root_id).where(
                        and_(
                            governance_root_authority_records.c.organization_id == org_id,
                            governance_root_authority_records.c.revoked_at.is_(None),
                        )
                    )
                )
            ).first()
            if existing_canon:
                raise root_already_exists("Concurrent attempt already established root authority.")

            # 3. Verify bootstrap record
            boot_row = (
                await conn.execute(
                    select(trust_fabric_bootstrap_records).where(
                        and_(
                            trust_fabric_bootstrap_records.c.org_id == org_id,
                            trust_fabric_bootstrap_records.c.nonce == nonce,
                        )
                    )
                )
            ).first()
            if not boot_row:
                raise bootstrap_invalid("No matching bootstrap ceremony record for this nonce.")

            rec = dict(boot_row._mapping)

            # Constant-time token hash comparison
            if not secrets.compare_digest(rec["token_hash"], token_hash):
                raise bootstrap_invalid("Bootstrap token does not match.")

            # Anti-replay check
            if rec["consumed_at"] is not None:
                raise bootstrap_replay("Bootstrap ceremony token has already been consumed.")

            # Expiry check
            if now_iso >= rec["expires_at"]:
                raise bootstrap_expired(f"Bootstrap ceremony expired at {rec['expires_at']}.")

            # Principal binding check
            if rec.get("claimed_by_principal_id") and rec["claimed_by_principal_id"] != actor.user_id:
                raise unauthorized_caller(
                    f"Ceremony is bound to principal {rec['claimed_by_principal_id']!r}, "
                    f"cannot be claimed by {actor.user_id!r}."
                )

            # Phishing-resistant WebAuthn Step-up check
            step_up_info = None
            if rec.get("require_passkey_stepup"):
                if not webauthn_assertion:
                    raise passkey_step_up_required(
                        "Phishing-resistant passkey step-up is required to complete root bootstrap."
                    )

            if webauthn_assertion:
                op_digest = compute_canonical_operation_digest(
                    "COMPLETE_ROOT_BOOTSTRAP",
                    {
                        "org_id": org_id,
                        "nonce": nonce,
                        "token_hash": token_hash,
                        "root_public_key": root_public_key,
                    },
                )
                step_up_info = await self._verify_webauthn_stepup_on_conn(
                    conn,
                    actor=actor,
                    org_id=org_id,
                    action="COMPLETE_ROOT_BOOTSTRAP",
                    operation_digest=op_digest,
                    assertion=webauthn_assertion,
                )

            # Root Key Proof of Possession (PoP)
            if root_signature:
                verify_root_proof_of_possession(
                    org_id=org_id,
                    nonce=nonce,
                    token_hash=token_hash,
                    root_public_key=root_public_key,
                    signature_b64=root_signature,
                )

            # 4. Mark ceremony record consumed (anti-replay)
            await conn.execute(
                update(trust_fabric_bootstrap_records)
                .where(trust_fabric_bootstrap_records.c.id == rec["id"])
                .values(consumed_at=now_iso, claimed_by_principal_id=actor.user_id)
            )

            # 5. Insert or update Trust Fabric Trust Root
            tf_root_id = f"wp_tfroot_{uuid.uuid4().hex}"
            tf_digest = compute_digest(
                {
                    "id": tf_root_id,
                    "org_id": org_id,
                    "root_principal_id": actor.user_id,
                    "root_public_key": root_public_key,
                    "established_at": now_iso,
                    "key_algorithm": key_algorithm,
                }
            )

            existing_tf_root = (
                await conn.execute(
                    select(trust_fabric_trust_roots.c.id).where(
                        trust_fabric_trust_roots.c.org_id == org_id
                    )
                )
            ).first()

            if existing_tf_root:
                await conn.execute(
                    update(trust_fabric_trust_roots)
                    .where(trust_fabric_trust_roots.c.org_id == org_id)
                    .values(
                        root_principal_id=actor.user_id,
                        root_public_key=root_public_key,
                        key_algorithm=key_algorithm,
                        established_at=now_iso,
                        status="ACTIVE",
                        canonical_digest=tf_digest,
                    )
                )
                tf_root_id = existing_tf_root[0]
            else:
                await conn.execute(
                    trust_fabric_trust_roots.insert().values(
                        id=tf_root_id,
                        org_id=org_id,
                        root_principal_id=actor.user_id,
                        root_public_key=root_public_key,
                        key_algorithm=key_algorithm,
                        established_at=now_iso,
                        status="ACTIVE",
                        canonical_digest=tf_digest,
                    )
                )

            # 6. Bridge into Canonical Governance: Root Authority Record
            canon_refs_list = list(evidence_refs or [f"bootstrap_nonce:{nonce}"])
            if step_up_info:
                canon_refs_list.append(f"webauthn_stepup:{step_up_info['credential_id']}")
            if root_signature:
                canon_refs_list.append("proof_of_possession:verified")
            canon_refs = tuple(canon_refs_list)

            canon_root_record = build_root_authority_record(
                subject_id=actor.user_id or "",
                root_type=RootType.HUMAN,
                issuer=f"customer:{actor.user_id}",
                verification_method="customer_bootstrap_ceremony",
                organization_id=org_id,
                jurisdiction="enterprise",
                evidence_refs=canon_refs,
                expires_at=now_dt + timedelta(days=365),
            )

            await conn.execute(
                governance_root_authority_records.insert().values(
                    root_id=canon_root_record.root_id,
                    subject_id=canon_root_record.subject_id,
                    root_type=canon_root_record.root_type.value,
                    organization_id=org_id,
                    issuer=canon_root_record.issuer,
                    verification_method=canon_root_record.verification_method,
                    authority_source=None,
                    jurisdiction=canon_root_record.jurisdiction,
                    evidence_refs=json.dumps(list(canon_root_record.evidence_refs)),
                    issued_at=canon_root_record.issued_at.isoformat(),
                    not_before=canon_root_record.not_before.isoformat() if canon_root_record.not_before else None,
                    expires_at=canon_root_record.expires_at.isoformat() if canon_root_record.expires_at else None,
                    revoked_at=None,
                    revoked_by=None,
                    revoke_reason=None,
                    canonical_digest=canon_root_record.canonical_digest,
                )
            )

            # 7. Bridge into Canonical Governance: Explicit Consent Proof
            cm_enum = ConsentMethod.SIGNED_DOCUMENT
            try:
                cm_enum = ConsentMethod(consent_method)
            except ValueError:
                cm_enum = ConsentMethod.SIGNED_DOCUMENT

            consent_record = build_consent_proof(
                subject_id=actor.user_id or "",
                consenting_root_id=canon_root_record.root_id,
                grantee_id=actor.user_id or "",
                scope_description=scope_description,
                purpose=purpose,
                consent_method=cm_enum,
                allowed_action_types=tuple(sorted(allowed_action_types)),
                allowed_targets=tuple(sorted(allowed_targets)),
                evidence_refs=canon_refs,
                expires_at=now_dt + timedelta(days=365),
            )

            await conn.execute(
                governance_consent_proofs.insert().values(
                    consent_id=consent_record.consent_id,
                    organization_id=org_id,
                    subject_id=consent_record.subject_id,
                    consenting_root_id=canon_root_record.root_id,
                    grantee_id=consent_record.grantee_id,
                    scope_description=consent_record.scope_description,
                    purpose=consent_record.purpose,
                    consent_method=consent_record.consent_method.value,
                    allowed_action_types=json.dumps(list(consent_record.allowed_action_types)),
                    allowed_targets=json.dumps(list(consent_record.allowed_targets)),
                    evidence_refs=json.dumps(list(consent_record.evidence_refs)),
                    consented_at=consent_record.consented_at.isoformat(),
                    not_before=consent_record.not_before.isoformat() if consent_record.not_before else None,
                    expires_at=consent_record.expires_at.isoformat() if consent_record.expires_at else None,
                    revoked_at=None,
                    revoked_by=None,
                    revoke_reason=None,
                    canonical_digest=consent_record.canonical_digest,
                )
            )

            # 8. Grant Initial Root Delegation to the Customer Owner
            delegation_id = str(uuid.uuid4())
            await conn.execute(
                governance_delegations.insert().values(
                    id=delegation_id,
                    org_id=org_id,
                    from_identity_id=None,
                    to_identity_id=actor.user_id,
                    granted_action_types=json.dumps(sorted(allowed_action_types)),
                    constraints=json.dumps({"allowed_targets": sorted(allowed_targets)}),
                    require_approval_for=None,
                    purpose=purpose,
                    granted_by=actor.user_id,
                    granted_at=now_iso,
                    expires_at=(now_dt + timedelta(days=365)).isoformat(),
                )
            )

            # 9. Authoritative Revocation Epoch Bump
            new_epoch = await bump_epoch_on_connection(conn, org_id)

            # 10. Durable Audit Evidence
            await self._audit.record(
                action="CUSTOMER_ROOT_AUTHORITY_BOOTSTRAPPED",
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
                org_id=org_id,
                target_type="root_authority",
                target_id=canon_root_record.root_id,
                result="SUCCESS",
                conn=conn,
                metadata={
                    "tf_root_id": tf_root_id,
                    "consent_id": consent_record.consent_id,
                    "delegation_id": delegation_id,
                    "nonce": nonce,
                    "epoch": new_epoch,
                    "passkey_verified": step_up_info is not None,
                    "proof_of_possession_verified": root_signature is not None,
                },
            )

        return {
            "status": "BOOTSTRAPPED",
            "organization_id": org_id,
            "root_id": canon_root_record.root_id,
            "consent_id": consent_record.consent_id,
            "delegation_id": delegation_id,
            "tf_root_id": tf_root_id,
            "subject_id": actor.user_id,
            "epoch": new_epoch,
            "established_at": now_iso,
            "canonical_digest": canon_root_record.canonical_digest,
            "passkey_verified": step_up_info is not None,
            "proof_of_possession_verified": root_signature is not None,
        }

    async def get_authority_status(self, actor: Actor, *, org_id: str) -> dict[str, Any]:
        """Query the organization's current customer root authority and consent status."""
        self._verify_tenant_and_role(actor, org_id)

        async with self._engine.raw.connect() as conn:
            root_row = (
                await conn.execute(
                    select(governance_root_authority_records)
                    .where(
                        and_(
                            governance_root_authority_records.c.organization_id == org_id,
                            governance_root_authority_records.c.revoked_at.is_(None),
                        )
                    )
                    .order_by(governance_root_authority_records.c.issued_at.desc())
                    .limit(1)
                )
            ).first()

            consent_row = None
            if root_row:
                consent_row = (
                    await conn.execute(
                        select(governance_consent_proofs)
                        .where(
                            and_(
                                governance_consent_proofs.c.organization_id == org_id,
                                governance_consent_proofs.c.consenting_root_id == root_row.root_id,
                                governance_consent_proofs.c.revoked_at.is_(None),
                            )
                        )
                        .order_by(governance_consent_proofs.c.consented_at.desc())
                        .limit(1)
                    )
                ).first()

            epoch = await self._epochs.current(org_id)

        has_active_authority = root_row is not None and consent_row is not None

        return {
            "organization_id": org_id,
            "has_active_authority": has_active_authority,
            "root_authority": {
                "root_id": root_row.root_id,
                "subject_id": root_row.subject_id,
                "issuer": root_row.issuer,
                "root_type": root_row.root_type,
                "verification_method": root_row.verification_method,
                "issued_at": root_row.issued_at,
                "expires_at": root_row.expires_at,
                "canonical_digest": root_row.canonical_digest,
            }
            if root_row
            else None,
            "consent_proof": {
                "consent_id": consent_row.consent_id,
                "scope_description": consent_row.scope_description,
                "purpose": consent_row.purpose,
                "consent_method": consent_row.consent_method,
                "allowed_action_types": json.loads(consent_row.allowed_action_types),
                "allowed_targets": json.loads(consent_row.allowed_targets),
                "consented_at": consent_row.consented_at,
                "canonical_digest": consent_row.canonical_digest,
            }
            if consent_row
            else None,
            "revocation_epoch": epoch.epoch,
        }

    async def revoke_root_authority(
        self,
        actor: Actor,
        *,
        org_id: str,
        root_id: str,
        reason: str,
    ) -> dict[str, Any]:
        """Revoke root authority, cascading to all consent proofs, delegations, and epochs."""
        self._verify_tenant_and_role(actor, org_id, require_owner=True)

        now_iso = _iso()
        async with self._engine.raw.begin() as conn:
            # 1. Lock and advance the revocation epoch
            new_epoch = await bump_epoch_on_connection(conn, org_id)

            # 2. Update canonical root authority
            root_res = await conn.execute(
                update(governance_root_authority_records)
                .where(
                    and_(
                        governance_root_authority_records.c.root_id == root_id,
                        governance_root_authority_records.c.organization_id == org_id,
                        governance_root_authority_records.c.revoked_at.is_(None),
                    )
                )
                .values(
                    revoked_at=now_iso,
                    revoked_by=actor.user_id,
                    revoke_reason=reason,
                )
            )
            if root_res.rowcount == 0:
                raise root_not_found(f"Active root authority {root_id!r} not found for tenant.")

            # 3. Revoke all associated consent proofs
            await conn.execute(
                update(governance_consent_proofs)
                .where(
                    and_(
                        governance_consent_proofs.c.consenting_root_id == root_id,
                        governance_consent_proofs.c.organization_id == org_id,
                        governance_consent_proofs.c.revoked_at.is_(None),
                    )
                )
                .values(
                    revoked_at=now_iso,
                    revoked_by=actor.user_id,
                    revoke_reason=f"Cascading revocation from root {root_id}: {reason}",
                )
            )

            # 4. Revoke Trust Fabric trust root
            await conn.execute(
                update(trust_fabric_trust_roots)
                .where(trust_fabric_trust_roots.c.org_id == org_id)
                .values(status="REVOKED")
            )

            # 5. Revoke all active delegations for the entire organization
            await conn.execute(
                update(governance_delegations)
                .where(
                    and_(
                        governance_delegations.c.org_id == org_id,
                        governance_delegations.c.revoked_at.is_(None),
                    )
                )
                .values(
                    revoked_at=now_iso,
                    revoked_by=actor.user_id,
                    revoke_reason=f"Root authority revoked: {reason}",
                )
            )

            # 6. Audit record
            await self._audit.record(
                action="CUSTOMER_ROOT_AUTHORITY_REVOKED",
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
                org_id=org_id,
                target_type="root_authority",
                target_id=root_id,
                result="SUCCESS",
                conn=conn,
                metadata={"reason": reason, "epoch": new_epoch},
            )

        # 7. Terminate in-flight executions
        try:
            from responsibleai.isolation.in_flight import InFlightExecutionRegistry
            await InFlightExecutionRegistry.get_instance().terminate_in_flight(organization_id=org_id)
        except Exception:
            pass

        return {
            "status": "REVOKED",
            "root_id": root_id,
            "organization_id": org_id,
            "revoked_at": now_iso,
            "new_epoch": new_epoch,
        }

    # ── Agent Management & Secure Identity Binding ────────────────────────────

    async def register_agent(
        self,
        actor: Actor,
        *,
        org_id: str,
        name: str,
        description: str = "",
        framework: str = "custom",
        purpose: str | None = None,
    ) -> dict[str, Any]:
        """Register an AI agent within the organization.

        INVARIANT: Registration does NOT grant authority. The agent is admitted to the
        identity directory as a distinct principal, but holds zero delegation grants.
        """
        self._verify_tenant_and_role(actor, org_id)

        if not name or not name.strip():
            raise consent_invalid("Agent name cannot be empty.")

        agent_id = f"agent_{uuid.uuid4().hex[:12]}"
        now_iso = _iso()
        meta = {
            "registered_by": actor.user_id,
            "framework": framework,
            "description": description,
            "purpose": purpose,
            "created_at": now_iso,
        }

        async with self._engine.raw.begin() as conn:
            await conn.execute(
                trust_fabric_principals.insert().values(
                    id=agent_id,
                    org_id=org_id,
                    principal_type=PrincipalType.AI_AGENT.value,
                    display_name=name.strip(),
                    lifecycle_state=PrincipalState.ACTIVE.value,
                    metadata_json=json.dumps(meta),
                    created_at=now_iso,
                    updated_at=now_iso,
                )
            )

            await self._audit.record(
                action="AGENT_REGISTERED",
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
                org_id=org_id,
                target_type="agent",
                target_id=agent_id,
                result="SUCCESS",
                conn=conn,
                metadata=meta,
            )

        return {
            "agent_id": agent_id,
            "organization_id": org_id,
            "display_name": name.strip(),
            "lifecycle_state": PrincipalState.ACTIVE.value,
            "framework": framework,
            "has_delegated_authority": False,
            "created_at": now_iso,
        }

    async def delegate_to_agent(
        self,
        actor: Actor,
        *,
        org_id: str,
        agent_id: str,
        granted_action_types: list[str],
        allowed_targets: list[str],
        purpose: str,
        expires_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Issue an explicit, attenuated delegation grant from an authorized principal to an agent."""
        self._verify_tenant_and_role(actor, org_id)

        # 1. Verify agent exists in this tenant
        async with self._engine.raw.connect() as conn:
            agent_row = (
                await conn.execute(
                    select(trust_fabric_principals).where(
                        and_(
                            trust_fabric_principals.c.id == agent_id,
                            trust_fabric_principals.c.org_id == org_id,
                        )
                    )
                )
            ).first()
            if not agent_row:
                raise agent_not_found(f"Agent {agent_id!r} not found in organization {org_id!r}.")

            agent_data = dict(agent_row._mapping)
            if agent_data["lifecycle_state"] != PrincipalState.ACTIVE.value:
                raise forbidden(FORBIDDEN, f"Agent {agent_id!r} is disabled or inactive.")

            # Query active root authority
            root_row = (
                await conn.execute(
                    select(governance_root_authority_records).where(
                        and_(
                            governance_root_authority_records.c.organization_id == org_id,
                            governance_root_authority_records.c.revoked_at.is_(None),
                        )
                    ).order_by(governance_root_authority_records.c.issued_at.desc())
                )
            ).first()
            if not root_row:
                raise root_not_found("No active root authority found for organization.")
            root_data = dict(root_row._mapping)

        # 2. Grant delegation with attenuation verification from actor
        delegation = await self._delegations.grant(
            org_id=org_id,
            to_identity_id=agent_id,
            from_identity_id=actor.user_id,
            granted_action_types=frozenset(granted_action_types),
            constraints={"allowed_targets": sorted(allowed_targets)},
            purpose=purpose,
            granted_by=actor.user_id or "system",
            expires_at=expires_at,
        )

        # 3. Create explicit attenuated consent proof for the agent bound to root authority
        agent_consent = build_consent_proof(
            subject_id=actor.user_id or root_data["subject_id"],
            consenting_root_id=root_data["root_id"],
            grantee_id=agent_id,
            scope_description=f"Explicit delegated consent for agent {agent_id}",
            purpose=purpose,
            consent_method=ConsentMethod.SIGNED_DOCUMENT,
            allowed_action_types=tuple(sorted(granted_action_types)),
            allowed_targets=tuple(sorted(allowed_targets)),
            evidence_refs=(f"delegation_grant:{delegation.delegation_id}",),
            expires_at=expires_at or (_now() + timedelta(days=90)),
        )

        async with self._engine.raw.begin() as conn:
            await conn.execute(
                governance_consent_proofs.insert().values(
                    consent_id=agent_consent.consent_id,
                    organization_id=org_id,
                    subject_id=agent_consent.subject_id,
                    consenting_root_id=agent_consent.consenting_root_id,
                    grantee_id=agent_consent.grantee_id,
                    scope_description=agent_consent.scope_description,
                    purpose=agent_consent.purpose,
                    consent_method=agent_consent.consent_method.value,
                    allowed_action_types=json.dumps(list(agent_consent.allowed_action_types)),
                    allowed_targets=json.dumps(list(agent_consent.allowed_targets)),
                    evidence_refs=json.dumps(list(agent_consent.evidence_refs)),
                    consented_at=agent_consent.consented_at.isoformat(),
                    not_before=agent_consent.not_before.isoformat() if agent_consent.not_before else None,
                    expires_at=agent_consent.expires_at.isoformat() if agent_consent.expires_at else None,
                    revoked_at=None,
                    revoked_by=None,
                    revoke_reason=None,
                    canonical_digest=agent_consent.canonical_digest,
                )
            )
            await self._audit.record(
                action="AGENT_DELEGATION_GRANTED",
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
                org_id=org_id,
                target_type="agent",
                target_id=agent_id,
                result="SUCCESS",
                conn=conn,
                metadata={
                    "delegation_id": delegation.delegation_id,
                    "consent_id": agent_consent.consent_id,
                    "granted_action_types": sorted(granted_action_types),
                    "allowed_targets": sorted(allowed_targets),
                    "purpose": purpose,
                },
            )

        return {
            "delegation_id": delegation.delegation_id,
            "consent_id": agent_consent.consent_id,
            "agent_id": agent_id,
            "organization_id": org_id,
            "granted_action_types": sorted(granted_action_types),
            "allowed_targets": sorted(allowed_targets),
            "purpose": purpose,
            "granted_at": delegation.granted_at.isoformat(),
        }

    async def disable_agent(
        self,
        actor: Actor,
        *,
        org_id: str,
        agent_id: str,
        reason: str = "Disabled by administrator",
    ) -> dict[str, Any]:
        """Disable an agent and revoke all its active delegations transitively."""
        self._verify_tenant_and_role(actor, org_id)

        now_iso = _iso()
        async with self._engine.raw.begin() as conn:
            # Update agent lifecycle state
            res = await conn.execute(
                update(trust_fabric_principals)
                .where(
                    and_(
                        trust_fabric_principals.c.id == agent_id,
                        trust_fabric_principals.c.org_id == org_id,
                    )
                )
                .values(lifecycle_state=PrincipalState.DISABLED.value, updated_at=now_iso)
            )
            if res.rowcount == 0:
                raise agent_not_found(f"Agent {agent_id!r} not found.")

            # Revoke consent proofs for this agent
            await conn.execute(
                update(governance_consent_proofs)
                .where(
                    and_(
                        governance_consent_proofs.c.organization_id == org_id,
                        governance_consent_proofs.c.grantee_id == agent_id,
                        governance_consent_proofs.c.revoked_at.is_(None),
                    )
                )
                .values(
                    revoked_at=now_iso,
                    revoked_by=actor.user_id,
                    revoke_reason=f"Agent {agent_id} disabled: {reason}",
                )
            )

        # Revoke all delegations for this agent branch (cascades and bumps epoch)
        revoked_delegations = await self._delegations.revoke_branch(
            org_id, agent_id, revoked_by=actor.user_id or "admin", reason=reason
        )

        async with self._engine.raw.begin() as conn:
            await self._audit.record(
                action="AGENT_DISABLED",
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
                org_id=org_id,
                target_type="agent",
                target_id=agent_id,
                result="SUCCESS",
                conn=conn,
                metadata={"reason": reason, "revoked_delegations": revoked_delegations},
            )

        return {
            "status": "DISABLED",
            "agent_id": agent_id,
            "organization_id": org_id,
            "revoked_delegations": revoked_delegations,
        }

    async def list_agents(self, actor: Actor, *, org_id: str) -> list[dict[str, Any]]:
        """List registered agents in the organization and their active delegation status."""
        self._verify_tenant_and_role(actor, org_id)

        async with self._engine.raw.connect() as conn:
            rows = (
                await conn.execute(
                    select(trust_fabric_principals).where(
                        and_(
                            trust_fabric_principals.c.org_id == org_id,
                            trust_fabric_principals.c.principal_type == PrincipalType.AI_AGENT.value,
                        )
                    )
                )
            ).fetchall()

            result = []
            for row in rows:
                data = dict(row._mapping)
                delegation = await self._delegations.get_active_delegation(org_id, data["id"])
                meta = {}
                if data.get("metadata_json"):
                    try:
                        meta = json.loads(data["metadata_json"])
                    except Exception:
                        pass
                result.append(
                    {
                        "agent_id": data["id"],
                        "organization_id": org_id,
                        "display_name": data["display_name"],
                        "lifecycle_state": data["lifecycle_state"],
                        "has_active_delegation": delegation is not None and delegation.is_active(),
                        "delegation_id": delegation.delegation_id if delegation else None,
                        "framework": meta.get("framework", "custom"),
                        "created_at": data["created_at"],
                    }
                )
            return result

    # ── Read-Only Reconciliation ──────────────────────────────────────────────

    async def reconcile_bootstrap_status(
        self,
        actor: Actor,
        *,
        org_id: str,
        token: str,
        nonce: str,
    ) -> dict[str, Any]:
        """Read-only deterministic status reconciliation for uncertain commit outcomes.

        Invariants:
        1. Read-only: Does NOT mint, re-issue, or mutate any root record or ceremony token.
        2. Atomic status lookup against PostgreSQL state.
        3. Reconciles whether an in-doubt bootstrap ceremony committed, expired, or remains pending.
        """
        self._verify_tenant_and_role(actor, org_id, require_owner=True)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        now_iso = _iso()

        async with self._engine.raw.connect() as conn:
            boot_row = (
                await conn.execute(
                    select(trust_fabric_bootstrap_records).where(
                        and_(
                            trust_fabric_bootstrap_records.c.org_id == org_id,
                            trust_fabric_bootstrap_records.c.nonce == nonce,
                        )
                    )
                )
            ).first()

            if not boot_row:
                return {
                    "organization_id": org_id,
                    "status": "NOT_FOUND",
                    "message": "No bootstrap ceremony found for this nonce.",
                }

            rec = dict(boot_row._mapping)
            if not secrets.compare_digest(rec["token_hash"], token_hash):
                return {
                    "organization_id": org_id,
                    "status": "TOKEN_MISMATCH",
                    "message": "Bootstrap token does not match record.",
                }

            if rec["consumed_at"] is not None:
                # Check if canonical root exists
                canon_root = (
                    await conn.execute(
                        select(governance_root_authority_records).where(
                            and_(
                                governance_root_authority_records.c.organization_id == org_id,
                                governance_root_authority_records.c.revoked_at.is_(None),
                            )
                        )
                    )
                ).first()

                epoch = await self._epochs.current(org_id)

                if canon_root:
                    return {
                        "organization_id": org_id,
                        "status": "COMMITTED",
                        "root_id": canon_root.root_id,
                        "consumed_at": rec["consumed_at"],
                        "revocation_epoch": epoch.epoch,
                        "canonical_digest": canon_root.canonical_digest,
                    }
                else:
                    return {
                        "organization_id": org_id,
                        "status": "CONSUMED_WITHOUT_ACTIVE_ROOT",
                        "consumed_at": rec["consumed_at"],
                        "revocation_epoch": epoch.epoch,
                    }

            # Not consumed: check if expired
            if now_iso >= rec["expires_at"]:
                return {
                    "organization_id": org_id,
                    "status": "EXPIRED",
                    "expires_at": rec["expires_at"],
                }

            return {
                "organization_id": org_id,
                "status": "PENDING_COMPLETION",
                "expires_at": rec["expires_at"],
                "claimed_by_principal_id": rec.get("claimed_by_principal_id"),
            }

    # ── Emergency Containment (Founder Decision B) ────────────────────────────

    async def execute_emergency_containment(
        self,
        actor: Actor,
        *,
        org_id: str,
        target_type: str,
        target_id: str,
        containment_action: str,
        reason: str,
        webauthn_assertion: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute single-owner emergency containment (kill-switch) without multi-admin quorum.

        Guarantees:
        - Zero residual privilege: atomically bumps revocation epoch and terminates in-flight executions.
        - Non-expansion invariant: emergency containment can ONLY reduce, suspend, or revoke authority;
          it CANNOT grant or expand authority.
        - Tenant isolation: caller must be Owner or Admin within the same tenant.
        """
        self._verify_tenant_and_role(actor, org_id)

        valid_targets = {"AGENT", "DELEGATION", "ROOT_AUTHORITY", "ORGANIZATION"}
        if target_type.upper() not in valid_targets:
            raise containment_invalid_target(f"Invalid target_type: {target_type!r}. Must be one of {valid_targets}")

        valid_actions = {"QUARANTINE", "REVOKE", "SUSPEND", "LOCKDOWN"}
        if containment_action.upper() not in valid_actions:
            raise containment_invalid_target(
                f"Invalid containment_action: {containment_action!r}. Must be one of {valid_actions}"
            )

        target_type = target_type.upper()
        containment_action = containment_action.upper()
        now_dt = _now()
        now_iso = _iso(now_dt)

        async with self._engine.raw.begin() as conn:
            # Step-up verification if assertion provided
            step_up_info = None
            if webauthn_assertion:
                op_digest = compute_canonical_operation_digest(
                    "EMERGENCY_CONTAINMENT",
                    {
                        "org_id": org_id,
                        "target_type": target_type,
                        "target_id": target_id,
                        "containment_action": containment_action,
                    },
                )
                step_up_info = await self._verify_webauthn_stepup_on_conn(
                    conn,
                    actor=actor,
                    org_id=org_id,
                    action="EMERGENCY_CONTAINMENT",
                    operation_digest=op_digest,
                    assertion=webauthn_assertion,
                )

            # 1. Authoritative epoch bump
            new_epoch = await bump_epoch_on_connection(conn, org_id)

            affected_records: dict[str, Any] = {}

            if target_type == "AGENT":
                # Target ID is agent principal ID
                res = await conn.execute(
                    update(trust_fabric_principals)
                    .where(
                        and_(
                            trust_fabric_principals.c.id == target_id,
                            trust_fabric_principals.c.org_id == org_id,
                        )
                    )
                    .values(lifecycle_state=PrincipalState.QUARANTINED.value, updated_at=now_iso)
                )
                if res.rowcount == 0:
                    raise agent_not_found(f"Agent {target_id!r} not found in organization.")

                c_res = await conn.execute(
                    update(governance_consent_proofs)
                    .where(
                        and_(
                            governance_consent_proofs.c.organization_id == org_id,
                            governance_consent_proofs.c.grantee_id == target_id,
                            governance_consent_proofs.c.revoked_at.is_(None),
                        )
                    )
                    .values(
                        revoked_at=now_iso,
                        revoked_by=actor.user_id,
                        revoke_reason=f"Emergency agent containment: {reason}",
                    )
                )
                affected_records["consent_proofs_revoked"] = c_res.rowcount

            elif target_type == "DELEGATION":
                d_res = await conn.execute(
                    update(governance_delegations)
                    .where(
                        and_(
                            governance_delegations.c.id == target_id,
                            governance_delegations.c.org_id == org_id,
                            governance_delegations.c.revoked_at.is_(None),
                        )
                    )
                    .values(
                        revoked_at=now_iso,
                        revoked_by=actor.user_id,
                        revoke_reason=f"Emergency delegation revocation: {reason}",
                    )
                )
                if d_res.rowcount == 0:
                    raise containment_invalid_target(f"Active delegation {target_id!r} not found in organization.")
                affected_records["delegations_revoked"] = d_res.rowcount

            elif target_type == "ROOT_AUTHORITY":
                r_res = await conn.execute(
                    update(governance_root_authority_records)
                    .where(
                        and_(
                            governance_root_authority_records.c.root_id == target_id,
                            governance_root_authority_records.c.organization_id == org_id,
                            governance_root_authority_records.c.revoked_at.is_(None),
                        )
                    )
                    .values(
                        revoked_at=now_iso,
                        revoked_by=actor.user_id,
                        revoke_reason=f"Emergency root revocation: {reason}",
                    )
                )
                if r_res.rowcount == 0:
                    raise root_not_found(f"Active root authority {target_id!r} not found in organization.")

                await conn.execute(
                    update(governance_consent_proofs)
                    .where(
                        and_(
                            governance_consent_proofs.c.consenting_root_id == target_id,
                            governance_consent_proofs.c.organization_id == org_id,
                            governance_consent_proofs.c.revoked_at.is_(None),
                        )
                    )
                    .values(
                        revoked_at=now_iso,
                        revoked_by=actor.user_id,
                        revoke_reason=f"Cascading emergency containment from root {target_id}: {reason}",
                    )
                )
                await conn.execute(
                    update(governance_delegations)
                    .where(
                        and_(
                            governance_delegations.c.org_id == org_id,
                            governance_delegations.c.revoked_at.is_(None),
                        )
                    )
                    .values(
                        revoked_at=now_iso,
                        revoked_by=actor.user_id,
                        revoke_reason=f"Emergency root containment: {reason}",
                    )
                )
                affected_records["root_revoked"] = target_id

            elif target_type == "ORGANIZATION":
                await conn.execute(
                    update(governance_delegations)
                    .where(
                        and_(
                            governance_delegations.c.org_id == org_id,
                            governance_delegations.c.revoked_at.is_(None),
                        )
                    )
                    .values(
                        revoked_at=now_iso,
                        revoked_by=actor.user_id,
                        revoke_reason=f"Organization emergency lockdown: {reason}",
                    )
                )
                await conn.execute(
                    update(governance_root_authority_records)
                    .where(
                        and_(
                            governance_root_authority_records.c.organization_id == org_id,
                            governance_root_authority_records.c.revoked_at.is_(None),
                        )
                    )
                    .values(
                        revoked_at=now_iso,
                        revoked_by=actor.user_id,
                        revoke_reason=f"Organization emergency lockdown: {reason}",
                    )
                )
                await conn.execute(
                    update(governance_consent_proofs)
                    .where(
                        and_(
                            governance_consent_proofs.c.organization_id == org_id,
                            governance_consent_proofs.c.revoked_at.is_(None),
                        )
                    )
                    .values(
                        revoked_at=now_iso,
                        revoked_by=actor.user_id,
                        revoke_reason=f"Organization emergency lockdown: {reason}",
                    )
                )
                await conn.execute(
                    update(trust_fabric_principals)
                    .where(
                        and_(
                            trust_fabric_principals.c.org_id == org_id,
                            trust_fabric_principals.c.principal_type == PrincipalType.AI_AGENT.value,
                        )
                    )
                    .values(lifecycle_state=PrincipalState.QUARANTINED.value, updated_at=now_iso)
                )
                affected_records["organization_lockdown"] = True

            # Insert containment record
            containment_id = f"wp_cnt_{uuid.uuid4().hex}"
            await conn.execute(
                authority_containment_records.insert().values(
                    id=containment_id,
                    org_id=org_id,
                    responder_user_id=actor.user_id,
                    target_type=target_type,
                    target_id=target_id,
                    containment_action=containment_action,
                    reason=reason,
                    status="CONTAINED",
                    revocation_epoch=new_epoch,
                    contained_at=now_iso,
                )
            )

            # Durable audit log
            await self._audit.record(
                action="EMERGENCY_CONTAINMENT_EXECUTED",
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
                org_id=org_id,
                target_type=target_type,
                target_id=target_id,
                result="SUCCESS",
                conn=conn,
                metadata={
                    "containment_id": containment_id,
                    "containment_action": containment_action,
                    "reason": reason,
                    "epoch": new_epoch,
                    "step_up": step_up_info is not None,
                },
            )

        # Invalidate in-flight executions
        try:
            from responsibleai.isolation.in_flight import InFlightExecutionRegistry
            await InFlightExecutionRegistry.get_instance().terminate_in_flight(organization_id=org_id)
        except Exception:
            pass

        return {
            "status": "CONTAINED",
            "containment_id": containment_id,
            "organization_id": org_id,
            "target_type": target_type,
            "target_id": target_id,
            "containment_action": containment_action,
            "revocation_epoch": new_epoch,
            "contained_at": now_iso,
            "affected_records": affected_records,
        }

    # ── M-of-N Quorum Recovery (Founder Decision B) ───────────────────────────

    async def create_recovery_request(
        self,
        actor: Actor,
        *,
        org_id: str,
        request_type: str,
        target_root_id: str,
        proposed_parameters: dict[str, Any],
        required_quorum_m: int = 2,
        eligible_quorum_n: int = 3,
        ttl_seconds: int = 86400,
    ) -> dict[str, Any]:
        """Initiate an M-of-N quorum recovery request."""
        self._verify_tenant_and_role(actor, org_id)

        if required_quorum_m < 1:
            raise consent_invalid("required_quorum_m must be at least 1.")
        if required_quorum_m > eligible_quorum_n:
            raise consent_invalid("required_quorum_m cannot exceed eligible_quorum_n.")

        action_digest = compute_canonical_operation_digest(
            request_type,
            {"org_id": org_id, "target_root_id": target_root_id, "params": proposed_parameters},
        )
        now_dt = _now()
        expires_at = _iso(now_dt + timedelta(seconds=ttl_seconds))
        request_id = f"wp_recov_{uuid.uuid4().hex}"

        async with self._engine.raw.begin() as conn:
            await conn.execute(
                authority_recovery_requests.insert().values(
                    id=request_id,
                    org_id=org_id,
                    request_type=request_type,
                    target_root_id=target_root_id,
                    requester_user_id=actor.user_id,
                    proposed_parameters_json=json.dumps(proposed_parameters),
                    action_digest=action_digest,
                    required_quorum_m=required_quorum_m,
                    eligible_quorum_n=eligible_quorum_n,
                    status="PENDING",
                    expires_at=expires_at,
                    executed_at=None,
                    executed_by_user_id=None,
                    created_at=_iso(now_dt),
                )
            )

            await self._audit.record(
                action="RECOVERY_REQUEST_CREATED",
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
                org_id=org_id,
                target_type="recovery_request",
                target_id=request_id,
                result="SUCCESS",
                conn=conn,
                metadata={
                    "request_type": request_type,
                    "target_root_id": target_root_id,
                    "required_quorum_m": required_quorum_m,
                    "eligible_quorum_n": eligible_quorum_n,
                    "action_digest": action_digest,
                },
            )

        return {
            "request_id": request_id,
            "organization_id": org_id,
            "request_type": request_type,
            "target_root_id": target_root_id,
            "requester_user_id": actor.user_id,
            "action_digest": action_digest,
            "required_quorum_m": required_quorum_m,
            "eligible_quorum_n": eligible_quorum_n,
            "status": "PENDING",
            "expires_at": expires_at,
        }

    async def vote_recovery_request(
        self,
        actor: Actor,
        *,
        org_id: str,
        request_id: str,
        decision: str,
        action_digest: str,
        notes: str = "",
        webauthn_assertion: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Cast an approval or rejection vote for a quorum recovery request."""
        self._verify_tenant_and_role(actor, org_id)

        decision = decision.upper()
        if decision not in {"APPROVE", "REJECT"}:
            raise consent_invalid("Decision must be APPROVE or REJECT.")

        now_dt = _now()
        now_iso = _iso(now_dt)

        async with self._engine.raw.begin() as conn:
            req_row = (
                await conn.execute(
                    select(authority_recovery_requests).where(
                        and_(
                            authority_recovery_requests.c.id == request_id,
                            authority_recovery_requests.c.org_id == org_id,
                        )
                    )
                )
            ).first()

            if not req_row:
                raise recovery_request_not_found(f"Recovery request {request_id!r} not found for organization.")

            req = dict(req_row._mapping)

            if req["status"] == "EXECUTED":
                raise recovery_already_executed("Recovery request has already been executed.")
            if req["status"] != "PENDING":
                raise recovery_request_not_found(f"Recovery request is {req['status']}, cannot accept votes.")

            if now_iso >= req["expires_at"]:
                raise recovery_expired(f"Recovery request expired at {req['expires_at']}.")

            if action_digest != req["action_digest"]:
                raise recovery_digest_mismatch(
                    f"Action digest mismatch: submitted {action_digest!r} != expected {req['action_digest']!r}."
                )

            # Anti-self-approval rule
            if decision == "APPROVE" and actor.user_id == req["requester_user_id"]:
                raise self_approval_blocked("Requester cannot approve their own recovery request.")

            # WebAuthn step-up if provided
            step_up_info = None
            if webauthn_assertion:
                step_up_info = await self._verify_webauthn_stepup_on_conn(
                    conn,
                    actor=actor,
                    org_id=org_id,
                    action="VOTE_RECOVERY_REQUEST",
                    operation_digest=action_digest,
                    assertion=webauthn_assertion,
                )

            # Anti-duplicate voting check
            existing_vote = (
                await conn.execute(
                    select(authority_recovery_votes).where(
                        and_(
                            authority_recovery_votes.c.request_id == request_id,
                            authority_recovery_votes.c.voter_user_id == actor.user_id,
                        )
                    )
                )
            ).first()
            if existing_vote:
                raise already_voted(f"User {actor.user_id!r} has already cast a vote for this request.")

            vote_id = f"wp_rvote_{uuid.uuid4().hex}"
            await conn.execute(
                authority_recovery_votes.insert().values(
                    id=vote_id,
                    request_id=request_id,
                    voter_user_id=actor.user_id,
                    decision=decision,
                    action_digest=action_digest,
                    voted_at=now_iso,
                    notes=notes,
                )
            )

            # If rejected, mark request as REJECTED
            if decision == "REJECT":
                await conn.execute(
                    update(authority_recovery_requests)
                    .where(authority_recovery_requests.c.id == request_id)
                    .values(status="REJECTED")
                )

            # Count total approvals
            approvals = (
                await conn.execute(
                    select(authority_recovery_votes).where(
                        and_(
                            authority_recovery_votes.c.request_id == request_id,
                            authority_recovery_votes.c.decision == "APPROVE",
                        )
                    )
                )
            ).fetchall()

            await self._audit.record(
                action="RECOVERY_REQUEST_VOTED",
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
                org_id=org_id,
                target_type="recovery_request",
                target_id=request_id,
                result="SUCCESS",
                conn=conn,
                metadata={
                    "vote_id": vote_id,
                    "decision": decision,
                    "approvals_count": len(approvals),
                    "required_quorum_m": req["required_quorum_m"],
                    "step_up": step_up_info is not None,
                },
            )

        return {
            "status": "VOTED",
            "request_id": request_id,
            "voter_user_id": actor.user_id,
            "decision": decision,
            "current_approvals": len(approvals),
            "required_quorum_m": req["required_quorum_m"],
            "request_status": "REJECTED" if decision == "REJECT" else "PENDING",
        }

    async def execute_recovery_request(
        self,
        actor: Actor,
        *,
        org_id: str,
        request_id: str,
        action_digest: str,
        webauthn_assertion: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute an approved quorum recovery request with pre-execution membership validation."""
        self._verify_tenant_and_role(actor, org_id)

        now_dt = _now()
        now_iso = _iso(now_dt)

        async with self._engine.raw.begin() as conn:
            # 1. Lock epoch to serialize recovery
            await lock_epoch(conn, org_id)

            req_row = (
                await conn.execute(
                    select(authority_recovery_requests).where(
                        and_(
                            authority_recovery_requests.c.id == request_id,
                            authority_recovery_requests.c.org_id == org_id,
                        )
                    )
                )
            ).first()

            if not req_row:
                raise recovery_request_not_found(f"Recovery request {request_id!r} not found for organization.")

            req = dict(req_row._mapping)

            if req["status"] == "EXECUTED":
                raise recovery_already_executed("Recovery request has already been executed.")
            if req["status"] != "PENDING":
                raise recovery_request_not_found(f"Recovery request is {req['status']}, cannot be executed.")

            if now_iso >= req["expires_at"]:
                raise recovery_expired(f"Recovery request expired at {req['expires_at']}.")

            if action_digest != req["action_digest"]:
                raise recovery_digest_mismatch(
                    f"Action digest mismatch: submitted {action_digest!r} != expected {req['action_digest']!r}."
                )

            # WebAuthn step-up if provided
            step_up_info = None
            if webauthn_assertion:
                step_up_info = await self._verify_webauthn_stepup_on_conn(
                    conn,
                    actor=actor,
                    org_id=org_id,
                    action="EXECUTE_RECOVERY_REQUEST",
                    operation_digest=action_digest,
                    assertion=webauthn_assertion,
                )

            # 2. Fetch all APPROVE votes
            votes = (
                await conn.execute(
                    select(authority_recovery_votes).where(
                        and_(
                            authority_recovery_votes.c.request_id == request_id,
                            authority_recovery_votes.c.decision == "APPROVE",
                        )
                    )
                )
            ).fetchall()

            # 3. Pre-execution recheck: ensure all approving voters are still active members/admins of org_id!
            valid_approver_ids: list[str] = []
            for v in votes:
                voter_id = v.voter_user_id
                mem = (
                    await conn.execute(
                        select(web_memberships).where(
                            and_(
                                web_memberships.c.user_id == voter_id,
                                web_memberships.c.org_id == org_id,
                                web_memberships.c.status == "ACTIVE",
                            )
                        )
                    )
                ).first()
                if mem:
                    valid_approver_ids.append(voter_id)

            if len(valid_approver_ids) < req["required_quorum_m"]:
                raise quorum_not_met(
                    f"Quorum threshold {req['required_quorum_m']} not satisfied (active verified approvals: {len(valid_approver_ids)})."
                )

            # 4. Bump revocation epoch
            new_epoch = await bump_epoch_on_connection(conn, org_id)

            req_type = req["request_type"].upper()
            params = json.loads(req["proposed_parameters_json"])

            if req_type in {"ROOT_TRANSFER", "ROOT_RECOVERY"}:
                target_root_id = req["target_root_id"]
                # Revoke old root
                await conn.execute(
                    update(governance_root_authority_records)
                    .where(
                        and_(
                            governance_root_authority_records.c.root_id == target_root_id,
                            governance_root_authority_records.c.organization_id == org_id,
                            governance_root_authority_records.c.revoked_at.is_(None),
                        )
                    )
                    .values(
                        revoked_at=now_iso,
                        revoked_by=actor.user_id,
                        revoke_reason=f"Quorum recovery execution ({req_type})",
                    )
                )
                # Revoke previous consent proofs
                await conn.execute(
                    update(governance_consent_proofs)
                    .where(
                        and_(
                            governance_consent_proofs.c.consenting_root_id == target_root_id,
                            governance_consent_proofs.c.organization_id == org_id,
                            governance_consent_proofs.c.revoked_at.is_(None),
                        )
                    )
                    .values(
                        revoked_at=now_iso,
                        revoked_by=actor.user_id,
                        revoke_reason=f"Quorum recovery execution ({req_type})",
                    )
                )

                new_subject_id = params.get("new_owner_user_id", actor.user_id)
                new_root_public_key = params.get("new_root_public_key", "")

                canon_root_record = build_root_authority_record(
                    subject_id=new_subject_id,
                    root_type=RootType.HUMAN,
                    issuer=f"quorum_recovery:{request_id}",
                    verification_method="quorum_multi_admin_recovery",
                    organization_id=org_id,
                    jurisdiction="enterprise",
                    evidence_refs=(f"recovery_request:{request_id}", f"quorum:{len(valid_approver_ids)}/{req['required_quorum_m']}"),
                    expires_at=now_dt + timedelta(days=365),
                )
                await conn.execute(
                    governance_root_authority_records.insert().values(
                        root_id=canon_root_record.root_id,
                        subject_id=canon_root_record.subject_id,
                        root_type=canon_root_record.root_type.value,
                        organization_id=org_id,
                        issuer=canon_root_record.issuer,
                        verification_method=canon_root_record.verification_method,
                        authority_source=None,
                        jurisdiction=canon_root_record.jurisdiction,
                        evidence_refs=json.dumps(list(canon_root_record.evidence_refs)),
                        issued_at=canon_root_record.issued_at.isoformat(),
                        not_before=canon_root_record.not_before.isoformat() if canon_root_record.not_before else None,
                        expires_at=canon_root_record.expires_at.isoformat() if canon_root_record.expires_at else None,
                        revoked_at=None,
                        revoked_by=None,
                        revoke_reason=None,
                        canonical_digest=canon_root_record.canonical_digest,
                    )
                )

                if new_root_public_key:
                    await conn.execute(
                        update(trust_fabric_trust_roots)
                        .where(trust_fabric_trust_roots.c.org_id == org_id)
                        .values(
                            root_principal_id=new_subject_id,
                            root_public_key=new_root_public_key,
                            established_at=now_iso,
                            status="ACTIVE",
                            canonical_digest=compute_digest({
                                "org_id": org_id,
                                "root_principal_id": new_subject_id,
                                "root_public_key": new_root_public_key,
                                "established_at": now_iso,
                            }),
                        )
                    )

                # Issue recovered consent proof
                scope_desc = params.get("scope_description", "Recovered root authority scope")
                purpose = params.get("purpose", "Administrative recovery")
                allowed_actions = params.get("allowed_action_types", ["*"])
                allowed_targets = params.get("allowed_targets", ["*"])
                new_consent = build_consent_proof(
                    subject_id=new_subject_id,
                    consenting_root_id=canon_root_record.root_id,
                    grantee_id=new_subject_id,
                    scope_description=scope_desc,
                    purpose=purpose,
                    consent_method=ConsentMethod.SIGNED_DOCUMENT,
                    allowed_action_types=tuple(sorted(allowed_actions)),
                    allowed_targets=tuple(sorted(allowed_targets)),
                    evidence_refs=(f"recovery_request:{request_id}",),
                    expires_at=now_dt + timedelta(days=365),
                )
                await conn.execute(
                    governance_consent_proofs.insert().values(
                        consent_id=new_consent.consent_id,
                        organization_id=org_id,
                        subject_id=new_consent.subject_id,
                        consenting_root_id=canon_root_record.root_id,
                        grantee_id=new_consent.grantee_id,
                        scope_description=new_consent.scope_description,
                        purpose=new_consent.purpose,
                        consent_method=new_consent.consent_method.value,
                        allowed_action_types=json.dumps(list(new_consent.allowed_action_types)),
                        allowed_targets=json.dumps(list(new_consent.allowed_targets)),
                        evidence_refs=json.dumps(list(new_consent.evidence_refs)),
                        consented_at=new_consent.consented_at.isoformat(),
                        not_before=new_consent.not_before.isoformat() if new_consent.not_before else None,
                        expires_at=new_consent.expires_at.isoformat() if new_consent.expires_at else None,
                        revoked_at=None,
                        revoked_by=None,
                        revoke_reason=None,
                        canonical_digest=new_consent.canonical_digest,
                    )
                )

            elif req_type == "KEY_ROTATION":
                new_root_public_key = params.get("new_root_public_key", "")
                if not new_root_public_key:
                    raise consent_invalid("new_root_public_key is required for KEY_ROTATION.")
                await conn.execute(
                    update(trust_fabric_trust_roots)
                    .where(trust_fabric_trust_roots.c.org_id == org_id)
                    .values(
                        root_public_key=new_root_public_key,
                        established_at=now_iso,
                        canonical_digest=compute_digest({
                            "org_id": org_id,
                            "root_public_key": new_root_public_key,
                            "established_at": now_iso,
                        }),
                    )
                )

            # Mark request as EXECUTED
            await conn.execute(
                update(authority_recovery_requests)
                .where(authority_recovery_requests.c.id == request_id)
                .values(
                    status="EXECUTED",
                    executed_at=now_iso,
                    executed_by_user_id=actor.user_id,
                )
            )

            # Record audit
            await self._audit.record(
                action="RECOVERY_REQUEST_EXECUTED",
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
                org_id=org_id,
                target_type="recovery_request",
                target_id=request_id,
                result="SUCCESS",
                conn=conn,
                metadata={
                    "request_type": req_type,
                    "approving_voters": list(valid_approver_ids),
                    "epoch": new_epoch,
                },
            )

        return {
            "status": "EXECUTED",
            "request_id": request_id,
            "organization_id": org_id,
            "request_type": req_type,
            "revocation_epoch": new_epoch,
            "executed_at": now_iso,
            "approving_voters_count": len(valid_approver_ids),
        }

    async def get_recovery_request(
        self,
        actor: Actor,
        *,
        org_id: str,
        request_id: str,
    ) -> dict[str, Any]:
        """Fetch status and vote history for a recovery request."""
        self._verify_tenant_and_role(actor, org_id)

        async with self._engine.raw.connect() as conn:
            req_row = (
                await conn.execute(
                    select(authority_recovery_requests).where(
                        and_(
                            authority_recovery_requests.c.id == request_id,
                            authority_recovery_requests.c.org_id == org_id,
                        )
                    )
                )
            ).first()

            if not req_row:
                raise recovery_request_not_found(f"Recovery request {request_id!r} not found for organization.")

            req = dict(req_row._mapping)

            votes = (
                await conn.execute(
                    select(authority_recovery_votes).where(
                        authority_recovery_votes.c.request_id == request_id
                    )
                )
            ).fetchall()

            vote_list = [dict(v._mapping) for v in votes]

        return {
            "request_id": req["id"],
            "organization_id": org_id,
            "request_type": req["request_type"],
            "target_root_id": req["target_root_id"],
            "requester_user_id": req["requester_user_id"],
            "proposed_parameters": json.loads(req["proposed_parameters_json"]),
            "action_digest": req["action_digest"],
            "required_quorum_m": req["required_quorum_m"],
            "eligible_quorum_n": req["eligible_quorum_n"],
            "status": req["status"],
            "expires_at": req["expires_at"],
            "executed_at": req.get("executed_at"),
            "executed_by_user_id": req.get("executed_by_user_id"),
            "created_at": req["created_at"],
            "votes": vote_list,
        }

    async def list_recovery_requests(
        self,
        actor: Actor,
        *,
        org_id: str,
    ) -> list[dict[str, Any]]:
        """List all recovery requests for the organization."""
        self._verify_tenant_and_role(actor, org_id)

        async with self._engine.raw.connect() as conn:
            rows = (
                await conn.execute(
                    select(authority_recovery_requests)
                    .where(authority_recovery_requests.c.org_id == org_id)
                    .order_by(authority_recovery_requests.c.created_at.desc())
                )
            ).fetchall()

            return [
                {
                    "request_id": r.id,
                    "organization_id": org_id,
                    "request_type": r.request_type,
                    "target_root_id": r.target_root_id,
                    "requester_user_id": r.requester_user_id,
                    "required_quorum_m": r.required_quorum_m,
                    "eligible_quorum_n": r.eligible_quorum_n,
                    "status": r.status,
                    "expires_at": r.expires_at,
                    "created_at": r.created_at,
                }
                for r in rows
            ]

