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

import asyncio
import fnmatch
import hashlib
import json
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
    governance_policies,
    governance_root_authority_records,
    org_authority_ceilings,
    org_security_policies,
    organizations,
    passkey_credentials,
    trust_fabric_bootstrap_records,
    trust_fabric_identifiers,
    trust_fabric_principals,
    trust_fabric_trust_roots,
    web_memberships,
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
    application_not_found,
    application_registration_invalid,
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
    CROSS_TENANT,
    FORBIDDEN,
    MEMBERSHIP_REVOKED,
    ORG_DISABLED,
    ORG_SUSPENDED,
    forbidden,
)
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
from responsibleai.rbac.models import GovernanceStatus, Role
from responsibleai.trust_fabric.directory import normalize_identifier
from responsibleai.trust_fabric.enums import (
    IdentifierType,
    IdentifierVerificationState,
    PrincipalState,
    PrincipalType,
)
from responsibleai.trust_fabric.models import compute_digest


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime | None = None) -> str:
    return (dt or _now()).isoformat()


def _parse_iso_dt(raw: str | datetime | None) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo is not None else raw.replace(tzinfo=UTC)
    s = str(raw).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def _is_temporally_valid(
    not_before_raw: str | datetime | None,
    expires_at_raw: str | datetime | None,
    now_dt: datetime,
) -> tuple[bool, bool]:
    """Return (is_valid, is_expired) for [not_before, expires_at)."""
    try:
        nb = _parse_iso_dt(not_before_raw)
        exp = _parse_iso_dt(expires_at_raw)
    except Exception:
        return False, False
    if nb is not None and now_dt < nb:
        return False, False
    if exp is not None and now_dt >= exp:
        return False, True
    return True, False


def _filter_targets_by_scope(targets: list[str], scope_patterns: list[str] | set[str]) -> list[str]:
    patterns = list(scope_patterns)
    if not patterns:
        return []
    if "*" in patterns:
        return list(targets)
    matched: list[str] = []
    for t in targets:
        if t == "*":
            for p in patterns:
                if p not in matched:
                    matched.append(p)
        elif any(t == p or fnmatch.fnmatchcase(t, p) for p in patterns):
            matched.append(t)
    return matched


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
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    try:
        # root_public_key may be hex or b64
        if len(root_public_key) == 64:
            pub_bytes = bytes.fromhex(root_public_key)
        else:
            pub_bytes = b64url_decode(root_public_key)

        sig_bytes = b64url_decode(signature_b64)
        message = f"WP_ROOT_POP:{org_id}:{nonce}:{token_hash}".encode()

        pub = Ed25519PublicKey.from_public_bytes(pub_bytes)
        pub.verify(sig_bytes, message)
    except Exception as exc:
        raise proof_of_possession_invalid(
            f"Proof of possession verification failed: {exc}"
        ) from exc


class CustomerAuthorityService:
    """Manages legitimate customer root authority, consent, and agent delegation."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine
        self._audit = EnterpriseAuditLog(engine)
        self._delegations = DelegationRepository(engine)
        self._epochs = RevocationEpochRepository(engine)

    def _verify_tenant_and_role(
        self, actor: Actor, org_id: str, require_owner: bool = False
    ) -> None:
        """Enforce authenticated tenant context and role authority."""
        if actor.org_id != org_id:
            raise forbidden(CROSS_TENANT, "Cross-tenant access strictly forbidden.")
        if require_owner:
            if actor.role != Role.OWNER:
                raise unauthorized_caller(
                    "This operation requires verified Organization Owner role."
                )
        else:
            if actor.role not in {Role.OWNER, Role.ADMIN}:
                raise unauthorized_caller(
                    "This operation requires Organization Owner or Admin role."
                )

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

        async with self._engine.raw.connect() as conn:
            # Enforce organization is active
            org_row = (
                await conn.execute(
                    select(
                        organizations.c.governance_status,
                        organizations.c.deactivated_at,
                    ).where(organizations.c.id == org_id)
                )
            ).first()
            if not org_row:
                raise forbidden(FORBIDDEN, f"Organization {org_id!r} not found.")
            if (
                org_row.governance_status == GovernanceStatus.DISABLED.value
                or org_row.deactivated_at
            ):
                raise forbidden(ORG_DISABLED, "Organization is disabled.")
            if org_row.governance_status == GovernanceStatus.SUSPENDED.value:
                raise forbidden(ORG_SUSPENDED, "Organization is suspended.")

            # Enforce caller membership in organization is active and owner
            m_row = (
                await conn.execute(
                    select(web_memberships.c.role, web_memberships.c.status).where(
                        and_(
                            web_memberships.c.org_id == org_id,
                            web_memberships.c.user_id == actor.user_id,
                        )
                    )
                )
            ).first()
            if not m_row or m_row.status != "ACTIVE":
                raise forbidden(MEMBERSHIP_REVOKED, "Caller membership is revoked or inactive.")
            if m_row.role != Role.OWNER.value:
                raise unauthorized_caller(
                    "This operation requires verified Organization Owner role."
                )

            # 1. Enforce actor account is not disabled or suspended
            u_row = (
                await conn.execute(
                    select(
                        web_users.c.disabled,
                        web_users.c.verification_status,
                        web_users.c.email_verified_at,
                    ).where(web_users.c.id == actor.user_id)
                )
            ).first()
            if (
                not u_row
                or u_row.disabled
                or u_row.verification_status in {"SUSPENDED", "REJECTED"}
            ):
                raise unauthorized_caller("User account is disabled, suspended, or rejected.")

            # 2. Enforce principal is not revoked in trust fabric if registered
            p_row = (
                await conn.execute(
                    select(
                        trust_fabric_principals.c.lifecycle_state,
                        trust_fabric_principals.c.org_id,
                    ).where(trust_fabric_principals.c.id == actor.user_id)
                )
            ).first()
            if p_row:
                if p_row.org_id != org_id:
                    raise unauthorized_caller(
                        f"Principal {actor.user_id!r} is registered to tenant {p_row.org_id!r}, cannot initiate root for {org_id!r}."
                    )
                if p_row.lifecycle_state in {
                    PrincipalState.REVOKED.value,
                    PrincipalState.SUSPENDED.value,
                    PrincipalState.DISABLED.value,
                    PrincipalState.DELETED.value,
                }:
                    raise unauthorized_caller(f"Principal identity is {p_row.lifecycle_state}.")

            # 3. Enforce identity assurance if required
            if require_identity_assurance:
                status = u_row.verification_status
                if status == "UNVERIFIED" and u_row.email_verified_at:
                    status = "BASIC_VERIFIED"
                if not status or status not in {"VERIFIED", "IDENTITY_VERIFIED", "BASIC_VERIFIED"}:
                    raise assurance_required()

            # 4. Check if organization has an active pending quorum recovery request
            pending_rec = (
                await conn.execute(
                    select(authority_recovery_requests.c.id).where(
                        and_(
                            authority_recovery_requests.c.org_id == org_id,
                            authority_recovery_requests.c.status == "PENDING",
                            authority_recovery_requests.c.expires_at > _iso(),
                        )
                    )
                )
            ).first()
            if pending_rec:
                raise root_already_exists("Organization has an active quorum recovery in progress.")

            # 5. Check if organization already possesses an active canonical root
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
                raise root_already_exists(
                    "Organization already has an active canonical root authority."
                )

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
        request: Any = None,
    ) -> dict[str, Any]:
        """Issue a short-lived, replay-resistant WebAuthn challenge bound to tenant, user, action, and digest."""
        self._verify_tenant_and_role(actor, org_id)

        from responsibleai.enterprise.security.router import resolve_webauthn_origin_and_rp_id

        origin, rp_id = resolve_webauthn_origin_and_rp_id(
            request,
            default_dev_origin="http://localhost:3000",
        )

        raw_challenge = secrets.token_bytes(32)
        challenge_b64 = b64url_encode(raw_challenge)
        challenge_hash = hashlib.sha256(challenge_b64.encode("utf-8")).hexdigest()

        now_dt = _now()
        expires_at_dt = now_dt + timedelta(seconds=ttl_seconds)
        expires_at = _iso(expires_at_dt)

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

    async def _verify_and_consume_path_b_authorization(
        self,
        conn: Any,
        *,
        actor: Actor,
        org_id: str,
        action: str,
        operation_digest: str,
        authorization_id: str,
    ) -> dict[str, Any]:
        """WP-M13-POL-002 Path B: Verify and atomically single-use consume pre-verified WebAuthn authorization."""
        now_iso = _iso()
        authz_hash = hashlib.sha256(authorization_id.encode("utf-8")).hexdigest()

        row = (
            await conn.execute(
                select(authority_step_up_challenges).where(
                    and_(
                        authority_step_up_challenges.c.challenge_hash == authz_hash,
                        authority_step_up_challenges.c.org_id == org_id,
                        authority_step_up_challenges.c.user_id == actor.user_id,
                    )
                )
            )
        ).first()

        if not row:
            raise webauthn_assertion_invalid(
                "No matching pre-verified step-up authorization found."
            )

        authz = dict(row._mapping)
        if authz["action"] != f"PREVERIFIED:{action}":
            raise webauthn_assertion_invalid(
                f"Authorization was issued for action {authz['action']!r}, not {action!r}."
            )

        if authz["operation_digest"] != operation_digest:
            raise webauthn_assertion_invalid(
                "Operation digest mismatch for pre-verified step-up authorization."
            )

        if authz["consumed_at"] is not None:
            raise webauthn_challenge_replay(
                "Pre-verified step-up authorization has already been consumed."
            )

        if now_iso >= authz["expires_at"]:
            raise webauthn_challenge_expired(
                f"Pre-verified step-up authorization expired at {authz['expires_at']}."
            )

        # Revalidate current responder authority dynamically: MUST still be ACTIVE OWNER or ADMIN
        mem = (
            await conn.execute(
                select(web_memberships).where(
                    and_(
                        web_memberships.c.user_id == actor.user_id,
                        web_memberships.c.org_id == org_id,
                        web_memberships.c.status == "ACTIVE",
                        web_memberships.c.role.in_(["OWNER", "ADMIN", "owner", "admin"]),
                    )
                )
            )
        ).first()
        if not mem:
            raise unauthorized_caller(
                "Caller membership or administrative role is no longer active."
            )

        # Revalidate user account status
        user_row = (
            await conn.execute(select(web_users).where(web_users.c.id == actor.user_id))
        ).first()
        if not user_row or user_row.disabled or user_row.verification_status == "SUSPENDED":
            raise unauthorized_caller("User account is disabled or suspended.")

        # Atomic single-use conditional consumption
        consume_res = await conn.execute(
            update(authority_step_up_challenges)
            .where(
                and_(
                    authority_step_up_challenges.c.challenge_hash == authz_hash,
                    authority_step_up_challenges.c.consumed_at.is_(None),
                )
            )
            .values(consumed_at=now_iso)
        )
        if consume_res.rowcount != 1:
            raise webauthn_challenge_replay(
                "Pre-verified step-up authorization has already been consumed."
            )

        return {
            "authorization_id": authorization_id,
            "user_id": actor.user_id,
            "org_id": org_id,
            "action": action,
            "consumed_at": now_iso,
            "path": "PATH_B_PREVERIFIED",
        }

    async def create_preverified_stepup_authorization(
        self,
        actor: Actor,
        *,
        org_id: str,
        action: str,
        operation: dict[str, Any],
        webauthn_assertion: dict[str, Any],
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """WP-M13-POL-002: Mint a server-verified, short-lived, operation-bound authorization ticket from a genuine WebAuthn ceremony."""
        self._verify_tenant_and_role(actor, org_id)

        # Restrict Path B exclusively to emergency containment; barred for root recovery or expansion
        if action != "EMERGENCY_CONTAINMENT":
            raise containment_forbidden(
                f"Pre-verified step-up authorization is strictly barred for action {action!r}."
            )

        op_digest = compute_canonical_operation_digest(action, operation)
        authz_id = f"wp_authz_{uuid.uuid4().hex}"
        authz_hash = hashlib.sha256(authz_id.encode("utf-8")).hexdigest()
        now_dt = _now()
        now_iso = _iso(now_dt)
        expires_at = _iso(now_dt + timedelta(seconds=300))  # 5-minute strict server-enforced expiry

        async with self._engine.raw.begin() as conn:
            # 1. Server verifies assertion against unconsumed challenge
            step_up_info = await self._verify_webauthn_stepup_on_conn(
                conn,
                actor=actor,
                org_id=org_id,
                action=action,
                operation_digest=op_digest,
                assertion=webauthn_assertion,
            )

            # 2. Store pre-verified authorization bound to principal, org, operation_digest, session
            await conn.execute(
                authority_step_up_challenges.insert().values(
                    challenge_hash=authz_hash,
                    org_id=org_id,
                    user_id=actor.user_id,
                    session_id=session_id,
                    action=f"PREVERIFIED:{action}",
                    operation_digest=op_digest,
                    rp_id=step_up_info.get("rp_id", "localhost"),
                    origin=step_up_info.get("origin", "http://localhost:3000"),
                    raw_challenge_b64=authz_id,
                    created_at=now_iso,
                    expires_at=expires_at,
                    consumed_at=None,
                )
            )

        return {
            "authorization_id": authz_id,
            "org_id": org_id,
            "user_id": actor.user_id,
            "action": action,
            "operation_digest": op_digest,
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
            raise webauthn_assertion_invalid(
                "No matching step-up challenge found for user, org, and challenge."
            )

        ch = dict(ch_row._mapping)
        if ch["action"] != action:
            raise webauthn_assertion_invalid(
                f"Step-up challenge was issued for action {ch['action']!r}, not {action!r}."
            )

        if ch["operation_digest"] != operation_digest:
            raise webauthn_assertion_invalid(
                "Operation digest mismatch between challenge and ceremony."
            )

        if ch["consumed_at"] is not None:
            raise webauthn_challenge_replay("Step-up challenge has already been consumed.")

        if now_iso >= ch["expires_at"]:
            raise webauthn_challenge_expired(f"Step-up challenge expired at {ch['expires_at']}.")

        # Mark challenge consumed atomically with conditional anti-replay check
        consume_res = await conn.execute(
            update(authority_step_up_challenges)
            .where(
                and_(
                    authority_step_up_challenges.c.challenge_hash == challenge_hash,
                    authority_step_up_challenges.c.consumed_at.is_(None),
                )
            )
            .values(consumed_at=now_iso)
        )
        if consume_res.rowcount != 1:
            raise webauthn_challenge_replay("Step-up challenge has already been consumed.")

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
            raise webauthn_assertion_invalid(
                f"WebAuthn assertion verification failed: {exc}"
            ) from exc

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

            # Enforce organization is active
            org_row = (
                await conn.execute(
                    select(
                        organizations.c.governance_status,
                        organizations.c.deactivated_at,
                    ).where(organizations.c.id == org_id)
                )
            ).first()
            if not org_row:
                raise forbidden(FORBIDDEN, f"Organization {org_id!r} not found.")
            if (
                org_row.governance_status == GovernanceStatus.DISABLED.value
                or org_row.deactivated_at
            ):
                raise forbidden(ORG_DISABLED, "Organization is disabled.")
            if org_row.governance_status == GovernanceStatus.SUSPENDED.value:
                raise forbidden(ORG_SUSPENDED, "Organization is suspended.")

            # Enforce caller membership in organization is active and owner
            m_row = (
                await conn.execute(
                    select(web_memberships.c.role, web_memberships.c.status).where(
                        and_(
                            web_memberships.c.org_id == org_id,
                            web_memberships.c.user_id == actor.user_id,
                        )
                    )
                )
            ).first()
            if not m_row or m_row.status != "ACTIVE":
                raise forbidden(MEMBERSHIP_REVOKED, "Caller membership is revoked or inactive.")
            if m_row.role != Role.OWNER.value:
                raise unauthorized_caller(
                    "This operation requires verified Organization Owner role."
                )

            # Enforce actor account is not disabled or suspended
            u_row = (
                await conn.execute(
                    select(
                        web_users.c.id,
                        web_users.c.full_name,
                        web_users.c.email,
                        web_users.c.disabled,
                        web_users.c.verification_status,
                        web_users.c.email_verified_at,
                    ).where(web_users.c.id == actor.user_id)
                )
            ).first()
            if (
                not u_row
                or u_row.disabled
                or u_row.verification_status in {"SUSPENDED", "REJECTED"}
            ):
                raise unauthorized_caller("User account is disabled, suspended, or rejected.")

            # Enforce principal is not revoked in trust fabric if registered
            p_row = (
                await conn.execute(
                    select(
                        trust_fabric_principals.c.id,
                        trust_fabric_principals.c.org_id,
                        trust_fabric_principals.c.lifecycle_state,
                    ).where(trust_fabric_principals.c.id == actor.user_id)
                )
            ).first()
            if p_row:
                if p_row.org_id != org_id:
                    raise unauthorized_caller(
                        f"Principal {actor.user_id!r} belongs to tenant {p_row.org_id!r}, cannot establish root for {org_id!r}."
                    )
                if p_row.lifecycle_state in {
                    PrincipalState.REVOKED.value,
                    PrincipalState.SUSPENDED.value,
                    PrincipalState.DISABLED.value,
                    PrincipalState.DELETED.value,
                }:
                    raise unauthorized_caller(f"Principal identity is {p_row.lifecycle_state}.")

            pending_rec = (
                await conn.execute(
                    select(authority_recovery_requests.c.id).where(
                        and_(
                            authority_recovery_requests.c.org_id == org_id,
                            authority_recovery_requests.c.status == "PENDING",
                            authority_recovery_requests.c.expires_at > now_iso,
                        )
                    )
                )
            ).first()
            if pending_rec:
                raise root_already_exists("Organization has an active quorum recovery in progress.")

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
            if (
                rec.get("claimed_by_principal_id")
                and rec["claimed_by_principal_id"] != actor.user_id
            ):
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

            # 5. Canonical Principal Enrollment & Identity Binding
            # Bridges verified web identity into Trust Fabric before root binding.
            if not p_row:
                display_name = (
                    u_row.full_name or u_row.email or f"Owner {actor.user_id[:8]}"
                ).strip()
                meta = {
                    "origin": "customer_root_bootstrap",
                    "email": u_row.email,
                    "established_at": now_iso,
                }
                if u_row.email_verified_at:
                    meta["verified_email"] = u_row.email
                await conn.execute(
                    trust_fabric_principals.insert().values(
                        id=actor.user_id,
                        org_id=org_id,
                        principal_type=PrincipalType.HUMAN.value,
                        display_name=display_name,
                        lifecycle_state=PrincipalState.ACTIVE.value,
                        created_at=now_iso,
                        updated_at=now_iso,
                        metadata_json=json.dumps(meta),
                    )
                )
            elif p_row.lifecycle_state == PrincipalState.PENDING_VERIFICATION.value:
                await conn.execute(
                    update(trust_fabric_principals)
                    .where(
                        and_(
                            trust_fabric_principals.c.id == actor.user_id,
                            trust_fabric_principals.c.org_id == org_id,
                        )
                    )
                    .values(
                        lifecycle_state=PrincipalState.ACTIVE.value,
                        updated_at=now_iso,
                    )
                )

            if u_row.email:
                norm_email = normalize_identifier(IdentifierType.EMAIL, u_row.email)
                chk_ident = (
                    await conn.execute(
                        select(
                            trust_fabric_identifiers.c.id,
                            trust_fabric_identifiers.c.principal_id,
                            trust_fabric_identifiers.c.verification_state,
                        ).where(
                            and_(
                                trust_fabric_identifiers.c.org_id == org_id,
                                trust_fabric_identifiers.c.identifier_type
                                == IdentifierType.EMAIL.value,
                                trust_fabric_identifiers.c.normalized_value == norm_email,
                                trust_fabric_identifiers.c.revoked_at.is_(None),
                            )
                        )
                    )
                ).first()
                if chk_ident and chk_ident.principal_id != actor.user_id:
                    raise unauthorized_caller(
                        f"Identifier EMAIL:{norm_email!r} is already claimed by principal {chk_ident.principal_id!r}."
                    )
                is_email_verified = bool(u_row.email_verified_at)
                v_state = (
                    IdentifierVerificationState.VERIFIED.value
                    if is_email_verified
                    else IdentifierVerificationState.UNVERIFIED.value
                )
                v_at = u_row.email_verified_at if is_email_verified else None
                if not chk_ident:
                    await conn.execute(
                        trust_fabric_identifiers.insert().values(
                            id=f"wp_ident_{uuid.uuid4().hex}",
                            principal_id=actor.user_id,
                            org_id=org_id,
                            identifier_type=IdentifierType.EMAIL.value,
                            raw_value=u_row.email,
                            normalized_value=norm_email,
                            is_primary=1,
                            verification_state=v_state,
                            verified_at=v_at,
                            expires_at=None,
                            revoked_at=None,
                            source_id="customer_root_bootstrap",
                            created_at=now_iso,
                        )
                    )
                elif (
                    is_email_verified
                    and chk_ident.verification_state != IdentifierVerificationState.VERIFIED.value
                ):
                    await conn.execute(
                        update(trust_fabric_identifiers)
                        .where(trust_fabric_identifiers.c.id == chk_ident.id)
                        .values(
                            verification_state=IdentifierVerificationState.VERIFIED.value,
                            verified_at=v_at,
                        )
                    )

            # 6. Insert or update Trust Fabric Trust Root
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

            # 7. Bridge into Canonical Governance: Root Authority Record
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
                    not_before=canon_root_record.not_before.isoformat()
                    if canon_root_record.not_before
                    else None,
                    expires_at=canon_root_record.expires_at.isoformat()
                    if canon_root_record.expires_at
                    else None,
                    revoked_at=None,
                    revoked_by=None,
                    revoke_reason=None,
                    canonical_digest=canon_root_record.canonical_digest,
                )
            )

            # 8. Bridge into Canonical Governance: Explicit Consent Proof
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
                    not_before=consent_record.not_before.isoformat()
                    if consent_record.not_before
                    else None,
                    expires_at=consent_record.expires_at.isoformat()
                    if consent_record.expires_at
                    else None,
                    revoked_at=None,
                    revoked_by=None,
                    revoke_reason=None,
                    canonical_digest=consent_record.canonical_digest,
                )
            )

            # 9. Grant Initial Root Delegation to the Customer Owner
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

            # 10. Authoritative Revocation Epoch Bump
            new_epoch = await bump_epoch_on_connection(conn, org_id)

            # 11. Durable Audit Evidence
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

        now_dt = _now()
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
                                governance_consent_proofs.c.grantee_id == root_row.subject_id,
                                governance_consent_proofs.c.revoked_at.is_(None),
                            )
                        )
                        .order_by(governance_consent_proofs.c.consented_at.desc())
                        .limit(1)
                    )
                ).first()
                if consent_row is None:
                    consent_row = (
                        await conn.execute(
                            select(governance_consent_proofs)
                            .where(
                                and_(
                                    governance_consent_proofs.c.organization_id == org_id,
                                    governance_consent_proofs.c.consenting_root_id
                                    == root_row.root_id,
                                    governance_consent_proofs.c.revoked_at.is_(None),
                                )
                            )
                            .order_by(governance_consent_proofs.c.consented_at.asc())
                            .limit(1)
                        )
                    ).first()

            epoch = await self._epochs.current(org_id)

        root_valid = (
            _is_temporally_valid(root_row.not_before, root_row.expires_at, now_dt)[0]
            if root_row
            else False
        )
        consent_valid = (
            _is_temporally_valid(consent_row.not_before, consent_row.expires_at, now_dt)[0]
            if consent_row
            else False
        )
        has_active_authority = bool(
            root_row is not None and consent_row is not None and root_valid and consent_valid
        )

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

            await InFlightExecutionRegistry.get_instance().terminate_in_flight(
                organization_id=org_id
            )
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
        application_id: str | None = None,
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
            "application_id": application_id,
            "created_at": now_iso,
        }

        async with self._engine.raw.begin() as conn:
            # Serialize against concurrent application disablement / revocation epoch mutations
            await lock_epoch(conn, org_id)

            if application_id:
                app_row = (
                    await conn.execute(
                        select(trust_fabric_principals).where(
                            and_(
                                trust_fabric_principals.c.id == application_id,
                                trust_fabric_principals.c.org_id == org_id,
                                trust_fabric_principals.c.principal_type
                                == PrincipalType.APPLICATION.value,
                            )
                        )
                    )
                ).first()
                if not app_row:
                    raise application_not_found(
                        f"Application {application_id!r} not found in organization {org_id!r}."
                    )
                if app_row.lifecycle_state != PrincipalState.ACTIVE.value:
                    raise forbidden(
                        FORBIDDEN, f"Application {application_id!r} is disabled or inactive."
                    )

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
            "application_id": application_id,
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

        now_dt = _now()
        async with self._engine.raw.begin() as conn:
            await lock_epoch(conn, org_id)

            # 1. Verify agent exists in this tenant and is ACTIVE
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

            agent_meta: dict[str, Any] = {}
            if agent_data.get("metadata_json"):
                try:
                    agent_meta = json.loads(agent_data["metadata_json"])
                except Exception:
                    agent_meta = {}
            parent_app_id = agent_meta.get("application_id")
            if parent_app_id:
                app_row = (
                    await conn.execute(
                        select(trust_fabric_principals).where(
                            and_(
                                trust_fabric_principals.c.id == parent_app_id,
                                trust_fabric_principals.c.org_id == org_id,
                                trust_fabric_principals.c.principal_type
                                == PrincipalType.APPLICATION.value,
                            )
                        )
                    )
                ).first()
                if not app_row or app_row.lifecycle_state != PrincipalState.ACTIVE.value:
                    raise forbidden(
                        FORBIDDEN,
                        f"Parent application {parent_app_id!r} for agent {agent_id!r} is disabled or inactive.",
                    )

            # Query active, non-expired root authority
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
                )
            ).first()
            if not root_row:
                raise root_not_found("No active root authority found for organization.")
            root_data = dict(root_row._mapping)
            root_valid, _ = _is_temporally_valid(
                root_data.get("not_before"),
                root_data.get("expires_at"),
                now_dt,
            )
            if not root_valid:
                raise root_not_found("Organization root authority is expired or not yet valid.")

            # 2. Grant delegation with attenuation verification from actor on the same transaction
            delegation = await self._delegations._grant_on_conn(
                conn,
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
                expires_at=expires_at or (now_dt + timedelta(days=90)),
            )

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
                    not_before=agent_consent.not_before.isoformat()
                    if agent_consent.not_before
                    else None,
                    expires_at=agent_consent.expires_at.isoformat()
                    if agent_consent.expires_at
                    else None,
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
        """Disable an agent and revoke all its active delegations transitively in a single transaction."""
        self._verify_tenant_and_role(actor, org_id)

        now_iso = _iso()
        async with self._engine.raw.begin() as conn:
            new_epoch = await bump_epoch_on_connection(conn, org_id)

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

            # Revoke all delegations for this agent branch on the same connection
            revoked_delegations = await self._delegations.revoke_branches_on_conn(
                conn,
                org_id,
                [agent_id],
                revoked_by=actor.user_id or "admin",
                reason=reason,
                bump_epoch=False,
            )

            await self._audit.record(
                action="AGENT_DISABLED",
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
                org_id=org_id,
                target_type="agent",
                target_id=agent_id,
                result="SUCCESS",
                conn=conn,
                metadata={
                    "reason": reason,
                    "revoked_delegations": revoked_delegations,
                    "revocation_epoch": new_epoch,
                },
            )

        return {
            "status": "DISABLED",
            "agent_id": agent_id,
            "organization_id": org_id,
            "revoked_delegations": revoked_delegations,
            "revocation_epoch": new_epoch,
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
                            trust_fabric_principals.c.principal_type
                            == PrincipalType.AI_AGENT.value,
                        )
                    )
                )
            ).fetchall()

            result = []
            for row in rows:
                data = dict(row._mapping)
                delegation = await self._delegations._get_active_delegation_on_conn(
                    conn, org_id, data["id"]
                )
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
                        "application_id": meta.get("application_id"),
                        "created_at": data["created_at"],
                    }
                )
            return result

    # ── Application Inventory & Tenant Ownership ──────────────────────────────

    async def register_application(
        self,
        actor: Actor,
        *,
        org_id: str,
        name: str,
        description: str = "",
        environment: str = "production",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Register a tenant-scoped application within the organization.

        INVARIANT: Registration does NOT grant execution authority. The application is
        admitted to the inventory with explicit lifecycle states, but cannot act or execute
        outside independently enforced authority.
        """
        self._verify_tenant_and_role(actor, org_id)

        if not name or not name.strip():
            raise application_registration_invalid("Application name cannot be empty.")

        app_id = f"app_{uuid.uuid4().hex[:12]}"
        now_iso = _iso()
        meta = {
            "registered_by": actor.user_id,
            "owner_user_id": actor.user_id,
            "environment": environment,
            "description": description.strip(),
            "custom_metadata": metadata or {},
            "created_at": now_iso,
        }

        async with self._engine.raw.begin() as conn:
            await conn.execute(
                trust_fabric_principals.insert().values(
                    id=app_id,
                    org_id=org_id,
                    principal_type=PrincipalType.APPLICATION.value,
                    display_name=name.strip(),
                    lifecycle_state=PrincipalState.ACTIVE.value,
                    metadata_json=json.dumps(meta),
                    created_at=now_iso,
                    updated_at=now_iso,
                )
            )

            await self._audit.record(
                action="APPLICATION_REGISTERED",
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
                org_id=org_id,
                target_type="application",
                target_id=app_id,
                result="SUCCESS",
                conn=conn,
                metadata=meta,
            )

        return {
            "application_id": app_id,
            "organization_id": org_id,
            "name": name.strip(),
            "description": description.strip(),
            "lifecycle_state": PrincipalState.ACTIVE.value,
            "environment": environment,
            "owner_user_id": actor.user_id,
            "has_execution_authority": False,
            "created_at": now_iso,
        }

    async def list_applications(self, actor: Actor, *, org_id: str) -> list[dict[str, Any]]:
        """List registered applications in the organization with agent counts and lifecycle states."""
        self._verify_tenant_and_role(actor, org_id)

        async with self._engine.raw.connect() as conn:
            app_rows = (
                await conn.execute(
                    select(trust_fabric_principals)
                    .where(
                        and_(
                            trust_fabric_principals.c.org_id == org_id,
                            trust_fabric_principals.c.principal_type
                            == PrincipalType.APPLICATION.value,
                        )
                    )
                    .order_by(trust_fabric_principals.c.created_at.desc())
                )
            ).fetchall()

            agent_rows = (
                await conn.execute(
                    select(trust_fabric_principals).where(
                        and_(
                            trust_fabric_principals.c.org_id == org_id,
                            trust_fabric_principals.c.principal_type
                            == PrincipalType.AI_AGENT.value,
                        )
                    )
                )
            ).fetchall()

            agent_counts: dict[str, int] = {}
            for a_row in agent_rows:
                a_data = dict(a_row._mapping)
                if a_data.get("metadata_json"):
                    try:
                        m = json.loads(a_data["metadata_json"])
                        app_ref = m.get("application_id")
                        if app_ref:
                            agent_counts[app_ref] = agent_counts.get(app_ref, 0) + 1
                    except Exception:
                        pass

            result = []
            for row in app_rows:
                data = dict(row._mapping)
                meta = {}
                if data.get("metadata_json"):
                    try:
                        meta = json.loads(data["metadata_json"])
                    except Exception:
                        pass
                result.append(
                    {
                        "application_id": data["id"],
                        "organization_id": org_id,
                        "name": data["display_name"],
                        "description": meta.get("description", ""),
                        "environment": meta.get("environment", "production"),
                        "owner_user_id": meta.get("owner_user_id"),
                        "lifecycle_state": data["lifecycle_state"],
                        "has_execution_authority": False,
                        "agent_count": agent_counts.get(data["id"], 0),
                        "created_at": data["created_at"],
                    }
                )
            return result

    async def get_application(self, actor: Actor, *, org_id: str, app_id: str) -> dict[str, Any]:
        """Get application details and its associated agents within the organization."""
        self._verify_tenant_and_role(actor, org_id)

        async with self._engine.raw.connect() as conn:
            app_row = (
                await conn.execute(
                    select(trust_fabric_principals).where(
                        and_(
                            trust_fabric_principals.c.id == app_id,
                            trust_fabric_principals.c.org_id == org_id,
                            trust_fabric_principals.c.principal_type
                            == PrincipalType.APPLICATION.value,
                        )
                    )
                )
            ).first()
            if not app_row:
                raise application_not_found(
                    f"Application {app_id!r} not found in organization {org_id!r}."
                )

            data = dict(app_row._mapping)
            meta = {}
            if data.get("metadata_json"):
                try:
                    meta = json.loads(data["metadata_json"])
                except Exception:
                    pass

            agent_rows = (
                await conn.execute(
                    select(trust_fabric_principals).where(
                        and_(
                            trust_fabric_principals.c.org_id == org_id,
                            trust_fabric_principals.c.principal_type
                            == PrincipalType.AI_AGENT.value,
                        )
                    )
                )
            ).fetchall()

            agents = []
            for a_row in agent_rows:
                a_data = dict(a_row._mapping)
                if a_data.get("metadata_json"):
                    try:
                        m = json.loads(a_data["metadata_json"])
                        if m.get("application_id") == app_id:
                            delegation = await self._delegations._get_active_delegation_on_conn(
                                conn, org_id, a_data["id"]
                            )
                            agents.append(
                                {
                                    "agent_id": a_data["id"],
                                    "display_name": a_data["display_name"],
                                    "lifecycle_state": a_data["lifecycle_state"],
                                    "has_active_delegation": delegation is not None
                                    and delegation.is_active(),
                                    "framework": m.get("framework", "custom"),
                                    "created_at": a_data["created_at"],
                                }
                            )
                    except Exception:
                        pass

            return {
                "application_id": data["id"],
                "organization_id": org_id,
                "name": data["display_name"],
                "description": meta.get("description", ""),
                "environment": meta.get("environment", "production"),
                "owner_user_id": meta.get("owner_user_id"),
                "lifecycle_state": data["lifecycle_state"],
                "has_execution_authority": False,
                "agents": agents,
                "created_at": data["created_at"],
                "updated_at": data["updated_at"],
            }

    async def disable_application(
        self,
        actor: Actor,
        *,
        org_id: str,
        app_id: str,
        reason: str = "Disabled by administrator",
    ) -> dict[str, Any]:
        """Disable an application and cascade disablement, consent revocation, and delegation revocation in one transaction."""
        self._verify_tenant_and_role(actor, org_id)

        now_iso = _iso()
        async with self._engine.raw.begin() as conn:
            # 1. Lock and advance the tenant revocation epoch in the same transaction
            new_epoch = await bump_epoch_on_connection(conn, org_id)

            res = await conn.execute(
                update(trust_fabric_principals)
                .where(
                    and_(
                        trust_fabric_principals.c.id == app_id,
                        trust_fabric_principals.c.org_id == org_id,
                        trust_fabric_principals.c.principal_type == PrincipalType.APPLICATION.value,
                    )
                )
                .values(lifecycle_state=PrincipalState.DISABLED.value, updated_at=now_iso)
            )
            if res.rowcount == 0:
                raise application_not_found(
                    f"Application {app_id!r} not found in organization {org_id!r}."
                )

            agent_rows = (
                await conn.execute(
                    select(trust_fabric_principals).where(
                        and_(
                            trust_fabric_principals.c.org_id == org_id,
                            trust_fabric_principals.c.principal_type
                            == PrincipalType.AI_AGENT.value,
                        )
                    )
                )
            ).fetchall()

            affected_agents: list[str] = []
            for a_row in agent_rows:
                a_data = dict(a_row._mapping)
                if a_data.get("metadata_json"):
                    try:
                        m = json.loads(a_data["metadata_json"])
                        if m.get("application_id") == app_id:
                            affected_agents.append(a_data["id"])
                    except Exception:
                        pass

            for agent_id in affected_agents:
                await conn.execute(
                    update(trust_fabric_principals)
                    .where(
                        and_(
                            trust_fabric_principals.c.id == agent_id,
                            trust_fabric_principals.c.org_id == org_id,
                        )
                    )
                    .values(lifecycle_state=PrincipalState.DISABLED.value, updated_at=now_iso)
                )
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
                        revoke_reason=f"Cascading disable from application {app_id}: {reason}",
                    )
                )

            all_revoked = await self._delegations.revoke_branches_on_conn(
                conn,
                org_id,
                affected_agents,
                revoked_by=actor.user_id or "admin",
                reason=f"Application {app_id} disabled: {reason}",
                bump_epoch=False,
            )

            await self._audit.record(
                action="APPLICATION_DISABLED",
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
                org_id=org_id,
                target_type="application",
                target_id=app_id,
                result="SUCCESS",
                conn=conn,
                metadata={
                    "reason": reason,
                    "cascaded_agents": affected_agents,
                    "revoked_delegations": all_revoked,
                    "revocation_epoch": new_epoch,
                },
            )

        try:
            from responsibleai.isolation.in_flight import InFlightExecutionRegistry

            InFlightExecutionRegistry.get_instance().record_revoked_epoch(org_id, new_epoch)
        except Exception:
            pass

        return {
            "status": "DISABLED",
            "application_id": app_id,
            "organization_id": org_id,
            "disabled_agents": affected_agents,
            "revoked_delegations": all_revoked,
            "revocation_epoch": new_epoch,
        }

    # ── Executable Capabilities ───────────────────────────────────────────────

    async def list_capabilities(
        self,
        actor: Actor,
        *,
        org_id: str,
        agent_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Server-authoritative enumeration of executable capabilities.

        INVARIANTS:
        1. Capabilities are server-authoritative and synthesized from verified root authority,
           governance consent proofs, explicit active delegations, parent application state,
           organization authority ceilings, and governance policies.
        2. No capability is ever inferred from frontend descriptions or user strings.
        3. Capability is reachability only; execution requires short-lived ExecutionAuthorization.
        """
        self._verify_tenant_and_role(actor, org_id)

        now_dt = _now()
        async with self._engine.raw.connect() as conn:
            # 1. Inspect canonical root authority records
            all_roots = (
                await conn.execute(
                    select(governance_root_authority_records)
                    .where(governance_root_authority_records.c.organization_id == org_id)
                    .order_by(governance_root_authority_records.c.issued_at.desc())
                )
            ).fetchall()

            latest_root: dict[str, Any] | None = dict(all_roots[0]._mapping) if all_roots else None
            active_root: dict[str, Any] | None = None
            root_state = "MISSING"

            for r in all_roots:
                r_dict = dict(r._mapping)
                if r_dict.get("revoked_at") is None:
                    r_valid, r_expired = _is_temporally_valid(
                        r_dict.get("not_before"),
                        r_dict.get("expires_at"),
                        now_dt,
                    )
                    if r_valid:
                        active_root = r_dict
                        root_state = "ACTIVE"
                    elif r_expired:
                        root_state = "EXPIRED"
                    else:
                        root_state = "REVOKED"
                    break
            else:
                if all_roots:
                    root_state = "REVOKED"

            # 2. Inspect root owner consent proof
            root_allowed_actions: set[str] = set()
            root_allowed_targets: list[str] = []
            if active_root is not None:
                rc_rows = (
                    await conn.execute(
                        select(governance_consent_proofs)
                        .where(
                            and_(
                                governance_consent_proofs.c.organization_id == org_id,
                                governance_consent_proofs.c.consenting_root_id
                                == active_root["root_id"],
                                governance_consent_proofs.c.grantee_id == active_root["subject_id"],
                            )
                        )
                        .order_by(governance_consent_proofs.c.consented_at.desc())
                    )
                ).fetchall()
                if not rc_rows:
                    rc_rows = (
                        await conn.execute(
                            select(governance_consent_proofs)
                            .where(
                                and_(
                                    governance_consent_proofs.c.organization_id == org_id,
                                    governance_consent_proofs.c.consenting_root_id
                                    == active_root["root_id"],
                                )
                            )
                            .order_by(governance_consent_proofs.c.consented_at.asc())
                        )
                    ).fetchall()
                if not rc_rows:
                    active_root = None
                    root_state = "REVOKED"
                else:
                    rc_latest = dict(rc_rows[0]._mapping)
                    if rc_latest.get("revoked_at") is not None:
                        active_root = None
                        root_state = "REVOKED"
                    else:
                        rc_valid, rc_expired = _is_temporally_valid(
                            rc_latest.get("not_before"),
                            rc_latest.get("expires_at"),
                            now_dt,
                        )
                        if not rc_valid:
                            active_root = None
                            root_state = "EXPIRED" if rc_expired else "REVOKED"
                        else:
                            root_allowed_actions = set(
                                json.loads(rc_latest.get("allowed_action_types") or "[]")
                            )
                            root_allowed_targets = list(
                                json.loads(rc_latest.get("allowed_targets") or "[]")
                            )

            # 3. Inspect org security policy, authority ceiling, and governance policies
            sec_pol_row = (
                await conn.execute(
                    select(org_security_policies).where(org_security_policies.c.org_id == org_id)
                )
            ).first()
            phishing_resistant_required = bool(
                sec_pol_row and getattr(sec_pol_row, "phishing_resistant_required", 0)
            )

            ceil_row = (
                await conn.execute(
                    select(org_authority_ceilings).where(org_authority_ceilings.c.org_id == org_id)
                )
            ).first()
            ceiling_allowed_actions: set[str] | None = None
            ceiling_allowed_targets: list[str] | None = None
            ceiling_denied_targets: set[str] = set()
            ceiling_require_approval_for: set[str] = set()
            if ceil_row is not None:
                c_map = dict(ceil_row._mapping)
                if c_map.get("allowed_action_types"):
                    ceiling_allowed_actions = set(json.loads(c_map["allowed_action_types"]))
                if c_map.get("allowed_targets"):
                    ceiling_allowed_targets = list(json.loads(c_map["allowed_targets"]))
                if c_map.get("denied_targets"):
                    ceiling_denied_targets = set(json.loads(c_map["denied_targets"]))
                if c_map.get("require_approval_for"):
                    ceiling_require_approval_for = set(json.loads(c_map["require_approval_for"]))

            pol_rows = (
                await conn.execute(
                    select(governance_policies)
                    .where(governance_policies.c.org_id == org_id)
                    .order_by(governance_policies.c.position.asc())
                )
            ).fetchall()
            policy_rules: list[dict[str, Any]] = []
            for p_row in pol_rows:
                p_map = dict(p_row._mapping)
                policy_rules.append(
                    {
                        "rule_id": p_map["rule_id"],
                        "effect": str(p_map["effect"]).upper(),
                        "action_types": set(json.loads(p_map["action_types"]))
                        if p_map.get("action_types")
                        else None,
                        "targets": set(json.loads(p_map["targets"]))
                        if p_map.get("targets")
                        else None,
                    }
                )

            # 4. Inspect tenant applications for parent lifecycle validation
            app_rows = (
                await conn.execute(
                    select(trust_fabric_principals).where(
                        and_(
                            trust_fabric_principals.c.org_id == org_id,
                            trust_fabric_principals.c.principal_type
                            == PrincipalType.APPLICATION.value,
                        )
                    )
                )
            ).fetchall()
            apps_by_id = {r.id: dict(r._mapping) for r in app_rows}

            # 5. Query agents
            query = select(trust_fabric_principals).where(
                and_(
                    trust_fabric_principals.c.org_id == org_id,
                    trust_fabric_principals.c.principal_type == PrincipalType.AI_AGENT.value,
                )
            )
            if agent_id:
                query = query.where(trust_fabric_principals.c.id == agent_id)

            agent_rows = (await conn.execute(query)).fetchall()
            if agent_id and not agent_rows:
                raise agent_not_found(f"Agent {agent_id!r} not found in organization {org_id!r}.")

            capabilities: list[dict[str, Any]] = []
            for a_row in agent_rows:
                a_data = dict(a_row._mapping)
                current_agent_id = a_data["id"]
                agent_state = a_data["lifecycle_state"]

                meta: dict[str, Any] = {}
                if a_data.get("metadata_json"):
                    try:
                        meta = json.loads(a_data["metadata_json"])
                    except Exception:
                        meta = {}
                app_ref = meta.get("application_id")
                app_is_active = True
                if app_ref is not None:
                    app_rec = apps_by_id.get(app_ref)
                    app_is_active = (
                        app_rec is not None
                        and app_rec.get("lifecycle_state") == PrincipalState.ACTIVE.value
                    )

                latest_del = await self._delegations._get_latest_delegation_on_conn(
                    conn, org_id, current_agent_id
                )
                active_del = await self._delegations._get_active_delegation_on_conn(
                    conn, org_id, current_agent_id
                )
                chain = (
                    await self._delegations._get_authority_chain_on_conn(
                        conn, org_id, current_agent_id
                    )
                    if active_del is not None
                    else []
                )
                chain_valid = bool(chain and chain[0].from_identity_id is None)

                # Query agent-specific consent proof
                ac_rows = (
                    await conn.execute(
                        select(governance_consent_proofs)
                        .where(
                            and_(
                                governance_consent_proofs.c.organization_id == org_id,
                                governance_consent_proofs.c.grantee_id == current_agent_id,
                            )
                        )
                        .order_by(governance_consent_proofs.c.consented_at.desc())
                    )
                ).fetchall()
                latest_ac: dict[str, Any] | None = dict(ac_rows[0]._mapping) if ac_rows else None
                active_ac: dict[str, Any] | None = None
                ac_state = "MISSING"
                if latest_ac is not None:
                    if latest_ac.get("revoked_at") is not None:
                        ac_state = "REVOKED"
                    else:
                        ac_valid, ac_expired = _is_temporally_valid(
                            latest_ac.get("not_before"),
                            latest_ac.get("expires_at"),
                            now_dt,
                        )
                        if ac_valid:
                            if (
                                active_root is not None
                                and latest_ac.get("consenting_root_id") == active_root["root_id"]
                            ):
                                active_ac = latest_ac
                                ac_state = "ACTIVE"
                            elif root_state == "EXPIRED":
                                ac_state = "EXPIRED"
                            else:
                                ac_state = "REVOKED"
                        elif ac_expired:
                            ac_state = "EXPIRED"
                        else:
                            ac_state = "REVOKED"

                if latest_del is None:
                    pending_status = (
                        "DISABLED"
                        if (agent_state != PrincipalState.ACTIVE.value or not app_is_active)
                        else "PENDING_DELEGATION"
                    )
                    cap_suffix = "default" if root_state != "ACTIVE" else "pending"
                    capabilities.append(
                        {
                            "capability_id": f"cap_{current_agent_id}_{cap_suffix}",
                            "agent_id": current_agent_id,
                            "organization_id": org_id,
                            "application_id": app_ref,
                            "kind": "DELEGATED_ACTION",
                            "action_type": "*",
                            "allowed_targets": [],
                            "status": pending_status,
                            "requires_approval": True,
                            "requires_passkey_stepup": phishing_resistant_required,
                            "root_id": active_root["root_id"]
                            if active_root
                            else (latest_root["root_id"] if latest_root else None),
                            "delegation_id": None,
                            "consent_id": None,
                            "constraints": {},
                            "authority_enforced": True,
                        }
                    )
                    continue

                del_expired = bool(
                    latest_del.expires_at is not None
                    and latest_del.revoked_at is None
                    and not latest_del.is_active()
                )
                if agent_state != PrincipalState.ACTIVE.value or not app_is_active:
                    base_status = "DISABLED"
                elif (
                    root_state == "REVOKED"
                    or latest_del.revoked_at is not None
                    or ac_state == "REVOKED"
                ):
                    base_status = "REVOKED"
                elif root_state == "EXPIRED" or del_expired or ac_state == "EXPIRED":
                    base_status = "EXPIRED"
                elif (
                    active_root is None
                    or active_del is None
                    or not chain_valid
                    or active_ac is None
                ):
                    base_status = "REVOKED"
                else:
                    base_status = "AUTHORIZED"

                ac_actions = (
                    set(json.loads(active_ac.get("allowed_action_types") or "[]"))
                    if active_ac
                    else set()
                )
                ac_targets = (
                    list(json.loads(active_ac.get("allowed_targets") or "[]")) if active_ac else []
                )

                for act in sorted(latest_del.granted_action_types):
                    cap_id = f"cap_{current_agent_id}_{act.replace(':', '_')}"
                    del_targets = list(latest_del.constraints.get("allowed_targets", []))
                    act_status = base_status
                    effective_targets = list(del_targets)

                    req_approval = bool(
                        act in latest_del.require_approval_for
                        or "*" in latest_del.require_approval_for
                        or act in ceiling_require_approval_for
                        or "*" in ceiling_require_approval_for
                    )
                    req_stepup = bool(
                        phishing_resistant_required
                        or latest_del.constraints.get("requires_passkey_stepup", False)
                    )

                    if act_status == "AUTHORIZED":
                        # Verify action is within root consent and agent consent
                        root_permits_act = (
                            "*" in root_allowed_actions or act in root_allowed_actions
                        )
                        ac_permits_act = "*" in ac_actions or act in ac_actions
                        ceil_permits_act = (
                            ceiling_allowed_actions is None
                            or "*" in ceiling_allowed_actions
                            or act in ceiling_allowed_actions
                        )
                        if not (root_permits_act and ac_permits_act and ceil_permits_act):
                            act_status = "POLICY_DENIED"
                            effective_targets = []
                        else:
                            effective_targets = _filter_targets_by_scope(
                                effective_targets, ac_targets
                            )
                            effective_targets = _filter_targets_by_scope(
                                effective_targets, root_allowed_targets
                            )
                            if ceiling_allowed_targets is not None:
                                effective_targets = _filter_targets_by_scope(
                                    effective_targets, ceiling_allowed_targets
                                )
                            if ceiling_denied_targets:
                                effective_targets = [
                                    t
                                    for t in effective_targets
                                    if not any(
                                        t == pat or fnmatch.fnmatchcase(t, pat)
                                        for pat in ceiling_denied_targets
                                    )
                                ]
                            if del_targets and not effective_targets:
                                act_status = "POLICY_DENIED"

                    if act_status == "AUTHORIZED" and policy_rules:
                        for rule in policy_rules:
                            r_actions = rule["action_types"]
                            if (
                                r_actions is not None
                                and "*" not in r_actions
                                and act not in r_actions
                            ):
                                continue
                            r_targets = rule["targets"]
                            effect = rule["effect"]
                            if r_targets is None or "*" in r_targets:
                                if effect in {"DENY", "QUARANTINE"}:
                                    act_status = "POLICY_DENIED"
                                    effective_targets = []
                                    req_approval = True
                                elif effect == "REQUIRE_APPROVAL":
                                    req_approval = True
                                break
                            else:
                                if effect in {"DENY", "QUARANTINE"}:
                                    effective_targets = [
                                        t
                                        for t in effective_targets
                                        if not any(
                                            t == pat or fnmatch.fnmatchcase(t, pat)
                                            for pat in r_targets
                                        )
                                    ]
                                    if del_targets and not effective_targets:
                                        act_status = "POLICY_DENIED"
                                        req_approval = True
                                        break
                                elif effect == "REQUIRE_APPROVAL":
                                    if any(
                                        t == "*"
                                        or any(
                                            t == pat or fnmatch.fnmatchcase(t, pat)
                                            for pat in r_targets
                                        )
                                        for t in effective_targets
                                    ):
                                        req_approval = True

                    if act_status != "AUTHORIZED":
                        req_approval = True

                    capabilities.append(
                        {
                            "capability_id": cap_id,
                            "agent_id": current_agent_id,
                            "organization_id": org_id,
                            "application_id": app_ref,
                            "kind": "DELEGATED_ACTION",
                            "action_type": act,
                            "allowed_targets": effective_targets,
                            "status": act_status,
                            "requires_approval": req_approval,
                            "requires_passkey_stepup": req_stepup,
                            "root_id": active_root["root_id"]
                            if (act_status == "AUTHORIZED" and active_root)
                            else (
                                active_root["root_id"]
                                if active_root
                                else (latest_root["root_id"] if latest_root else None)
                            ),
                            "delegation_id": active_del.delegation_id
                            if (act_status == "AUTHORIZED" and active_del)
                            else latest_del.delegation_id,
                            "consent_id": active_ac["consent_id"]
                            if (act_status == "AUTHORIZED" and active_ac)
                            else (latest_ac["consent_id"] if latest_ac else None),
                            "constraints": latest_del.constraints,
                            "authority_enforced": True,
                        }
                    )

            return capabilities

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
        stepup_authorization_id: str | None = None,
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
            raise containment_invalid_target(
                f"Invalid target_type: {target_type!r}. Must be one of {valid_targets}"
            )

        valid_actions = {"QUARANTINE", "REVOKE", "SUSPEND", "LOCKDOWN"}
        if containment_action.upper() not in valid_actions:
            raise containment_invalid_target(
                f"Invalid containment_action: {containment_action!r}. Must be one of {valid_actions}"
            )

        # Phishing-resistant WebAuthn Step-up check (Founder Decision A/B & WP-M13-POL-002)
        if not webauthn_assertion and not stepup_authorization_id:
            raise passkey_step_up_required(
                "Phishing-resistant passkey step-up is required for emergency containment."
            )

        target_type = target_type.upper()
        containment_action = containment_action.upper()
        now_dt = _now()
        now_iso = _iso(now_dt)

        op_digest = compute_canonical_operation_digest(
            "EMERGENCY_CONTAINMENT",
            {
                "org_id": org_id,
                "target_type": target_type,
                "target_id": target_id,
                "containment_action": containment_action,
            },
        )

        containment_id = f"wp_cnt_{uuid.uuid4().hex}"

        async with self._engine.raw.begin() as conn:
            # Step-up verification: Path A (fresh assertion) or Path B (pre-verified authorization)
            if webauthn_assertion:
                step_up_info = await self._verify_webauthn_stepup_on_conn(
                    conn,
                    actor=actor,
                    org_id=org_id,
                    action="EMERGENCY_CONTAINMENT",
                    operation_digest=op_digest,
                    assertion=webauthn_assertion,
                )
            else:
                step_up_info = await self._verify_and_consume_path_b_authorization(
                    conn,
                    actor=actor,
                    org_id=org_id,
                    action="EMERGENCY_CONTAINMENT",
                    operation_digest=op_digest,
                    authorization_id=stepup_authorization_id,  # type: ignore[arg-type]
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
                    raise containment_invalid_target(
                        f"Active delegation {target_id!r} not found in organization."
                    )
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
                    raise root_not_found(
                        f"Active root authority {target_id!r} not found in organization."
                    )

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
                            trust_fabric_principals.c.principal_type
                            == PrincipalType.AI_AGENT.value,
                        )
                    )
                    .values(lifecycle_state=PrincipalState.QUARANTINED.value, updated_at=now_iso)
                )
                affected_records["organization_lockdown"] = True

            # Insert containment record with durable status TERMINATION_PENDING before attempting termination
            await conn.execute(
                authority_containment_records.insert().values(
                    id=containment_id,
                    org_id=org_id,
                    responder_user_id=actor.user_id,
                    target_type=target_type,
                    target_id=target_id,
                    containment_action=containment_action,
                    reason=reason,
                    status="TERMINATION_PENDING",
                    revocation_epoch=new_epoch,
                    contained_at=now_iso,
                )
            )

            # Durable audit log recording admission lock
            await self._audit.record(
                action="EMERGENCY_CONTAINMENT_ADMISSION_LOCKED",
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
                org_id=org_id,
                target_type=target_type,
                target_id=target_id,
                result="TERMINATION_PENDING",
                conn=conn,
                metadata={
                    "containment_id": containment_id,
                    "containment_action": containment_action,
                    "reason": reason,
                    "epoch": new_epoch,
                    "status": "TERMINATION_PENDING",
                    "step_up": True,
                    "auth_path": step_up_info.get("path", "PATH_A_ASSERTION"),
                },
            )

        # Record latest revoked epoch in in-flight registry
        try:
            from responsibleai.isolation.in_flight import InFlightExecutionRegistry

            InFlightExecutionRegistry.get_instance().record_revoked_epoch(org_id, new_epoch)
        except Exception:
            pass

        # Invalidate in-flight executions before finalizing containment status
        containment_status = "CONTAINED"
        termination_error: str | None = None
        try:
            from responsibleai.isolation.in_flight import InFlightExecutionRegistry

            registry = InFlightExecutionRegistry.get_instance()
            await registry.terminate_in_flight(organization_id=org_id)
            if registry.count_unresolved(org_id) > 0:
                containment_status = "UNRESOLVED"
        except asyncio.CancelledError:
            # Cancellation preserves durable incident record with TERMINATION_PENDING
            raise
        except Exception as exc:
            containment_status = "UNRESOLVED"
            termination_error = str(exc)

        # Update containment record and audit log with confirmed vs unresolved status
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                update(authority_containment_records)
                .where(authority_containment_records.c.id == containment_id)
                .values(status=containment_status)
            )

            # Durable audit log
            await self._audit.record(
                action="EMERGENCY_CONTAINMENT_EXECUTED",
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
                org_id=org_id,
                target_type=target_type,
                target_id=target_id,
                result="SUCCESS" if containment_status == "CONTAINED" else "UNRESOLVED",
                conn=conn,
                metadata={
                    "containment_id": containment_id,
                    "containment_action": containment_action,
                    "reason": reason,
                    "epoch": new_epoch,
                    "status": containment_status,
                    "step_up": step_up_info is not None,
                    "auth_path": step_up_info.get("path", "PATH_A_ASSERTION"),
                    "termination_error": termination_error,
                },
            )

        ret: dict[str, Any] = {
            "status": containment_status,
            "containment_id": containment_id,
            "organization_id": org_id,
            "target_type": target_type,
            "target_id": target_id,
            "containment_action": containment_action,
            "revocation_epoch": new_epoch,
            "contained_at": now_iso,
            "affected_records": affected_records,
        }
        if termination_error is not None:
            ret["termination_error"] = termination_error
        return ret

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
                raise recovery_request_not_found(
                    f"Recovery request {request_id!r} not found for organization."
                )

            req = dict(req_row._mapping)

            if req["status"] == "EXECUTED":
                raise recovery_already_executed("Recovery request has already been executed.")
            if req["status"] != "PENDING":
                raise recovery_request_not_found(
                    f"Recovery request is {req['status']}, cannot accept votes."
                )

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
                raise already_voted(
                    f"User {actor.user_id!r} has already cast a vote for this request."
                )

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
                raise recovery_request_not_found(
                    f"Recovery request {request_id!r} not found for organization."
                )

            req = dict(req_row._mapping)

            if req["status"] == "EXECUTED":
                raise recovery_already_executed("Recovery request has already been executed.")
            if req["status"] != "PENDING":
                raise recovery_request_not_found(
                    f"Recovery request is {req['status']}, cannot be executed."
                )

            if now_iso >= req["expires_at"]:
                raise recovery_expired(f"Recovery request expired at {req['expires_at']}.")

            if action_digest != req["action_digest"]:
                raise recovery_digest_mismatch(
                    f"Action digest mismatch: submitted {action_digest!r} != expected {req['action_digest']!r}."
                )

            if webauthn_assertion:
                await self._verify_webauthn_stepup_on_conn(
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

            # 3. Pre-execution dynamic recheck: ensure all approving voters are still active admins/owners of org_id!
            valid_approver_ids: list[str] = []
            seen_voters: set[str] = set()
            for v in votes:
                voter_id = v.voter_user_id
                if voter_id in seen_voters:
                    continue
                seen_voters.add(voter_id)

                # Anti-self-approval recheck
                if voter_id == req["requester_user_id"]:
                    continue

                mem = (
                    await conn.execute(
                        select(web_memberships).where(
                            and_(
                                web_memberships.c.user_id == voter_id,
                                web_memberships.c.org_id == org_id,
                                web_memberships.c.status == "ACTIVE",
                                web_memberships.c.role.in_(["OWNER", "ADMIN", "owner", "admin"]),
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
                    evidence_refs=(
                        f"recovery_request:{request_id}",
                        f"quorum:{len(valid_approver_ids)}/{req['required_quorum_m']}",
                    ),
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
                        not_before=canon_root_record.not_before.isoformat()
                        if canon_root_record.not_before
                        else None,
                        expires_at=canon_root_record.expires_at.isoformat()
                        if canon_root_record.expires_at
                        else None,
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
                            canonical_digest=compute_digest(
                                {
                                    "org_id": org_id,
                                    "root_principal_id": new_subject_id,
                                    "root_public_key": new_root_public_key,
                                    "established_at": now_iso,
                                }
                            ),
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
                        not_before=new_consent.not_before.isoformat()
                        if new_consent.not_before
                        else None,
                        expires_at=new_consent.expires_at.isoformat()
                        if new_consent.expires_at
                        else None,
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
                        canonical_digest=compute_digest(
                            {
                                "org_id": org_id,
                                "root_public_key": new_root_public_key,
                                "established_at": now_iso,
                            }
                        ),
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
                raise recovery_request_not_found(
                    f"Recovery request {request_id!r} not found for organization."
                )

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
