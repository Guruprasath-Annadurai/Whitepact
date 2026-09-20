# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Identity security service: passkeys, TOTP, recovery, sessions, providers, SSO.

Redis is never canonical. Failures deny. This module cannot mint ExecutionAuthorization.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError

from responsibleai.auth import mfa
from responsibleai.auth.saml import SAMLConfig, parse_and_validate_response
from responsibleai.db.engine import (
    DatabaseEngine,
    account_recovery_requests,
    auth_replay_records,
    company_domain_challenges,
    human_totp_factors,
    identity_security_notifications,
    org_security_policies,
    organization_idp_bindings,
    organization_sso_configs,
    organization_verifications,
    organizations,
    passkey_credentials,
    provider_identities,
    recovery_code_hashes,
    step_up_grants,
    web_memberships,
    web_sessions,
    web_users,
    webauthn_challenges,
)
from responsibleai.enterprise.audit import EnterpriseAuditLog
from responsibleai.enterprise.errors import (
    ACCOUNT_LINK_CONFLICT,
    AUTHENTICATION_FAILED,
    BREAK_GLASS_DENIED,
    CHALLENGE_REPLAY,
    COMPANY_VERIFICATION_REQUIRED,
    ENTRA_TENANT_MISMATCH,
    GOOGLE_WORKSPACE_MISMATCH,
    LAST_AUTH_METHOD,
    MFA_REQUIRED,
    PASSKEY_REQUIRED,
    PROVIDER_TOKEN_INVALID,
    RECOVERY_REVIEW_REQUIRED,
    SECURITY_DOWNGRADE_BLOCKED,
    SSO_REQUIRED,
    SSO_TENANT_MISMATCH,
    STEP_UP_REQUIRED,
    WEBAUTHN_INVALID,
    EnterpriseError,
    forbidden,
    unauthenticated,
)
from responsibleai.enterprise.security.assurance import SESSION_LEVEL, map_authentication_assurance
from responsibleai.enterprise.security.four_eyes import (
    DEFAULT_DUAL_CONTROL_ACTIONS,
    IdentityFourEyesService,
)
from responsibleai.enterprise.security.oauth import (
    GOOGLE_ISSUER,
    MICROSOFT_JWKS,
    HostedOAuthService,
)
from responsibleai.enterprise.security.oidc import (
    GOOGLE_ISSUERS,
    MSA_TENANT,
    OIDCTokenValidator,
    VerifiedIDToken,
)
from responsibleai.enterprise.security.policy import (
    ASSURANCE_RANK,
    AuthenticationSecurityPolicy,
    AuthMethod,
    OrgAuthPolicy,
    SensitiveAction,
    SessionAssurance,
)
from responsibleai.enterprise.security.providers import canonicalize_provider, provider_account_key
from responsibleai.enterprise.security.rate_limit import DurableIdentityRateLimiter
from responsibleai.enterprise.security.webauthn import (
    b64url_decode,
    b64url_encode,
    verify_assertion,
    verify_registration,
)
from responsibleai.net.egress import DestinationPolicy, validate_outbound_url
from responsibleai.rbac.models import Role
from responsibleai.runtime.gate import PRODUCTION_GATE_B_OPEN

_CHALLENGE_TTL = 120
_STEP_UP_TTL = 180
_RECOVERY_TTL = 900
_SESSION_ABSOLUTE_HOURS = 12
_SESSION_IDLE_HOURS = 2
_RECOVERY_CODES = 10
_CODE_LEN = 10
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
GOOGLE_PROVIDER = "GOOGLE"
GOOGLE_WORKSPACE = "GOOGLE_WORKSPACE"
MICROSOFT_PROVIDER = "MICROSOFT"
ENTRA_PROVIDER = "MICROSOFT_ENTRA"


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).isoformat()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class IdentitySecurityService:
    engine: DatabaseEngine
    rp_id: str = "localhost"
    origin: str = "http://localhost"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_jwks_url: str = "https://www.googleapis.com/oauth2/v3/certs"
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_jwks_url: str = "https://login.microsoftonline.com/common/discovery/v2.0/keys"
    hosted_redirect_uri: str = "https://localhost/api/enterprise/identity-providers/callback"
    allow_raw_id_token: bool = False
    txt_lookup: Callable[[str], list[str]] | None = None
    well_known_lookup: Callable[[str], str | None] | None = None
    policy: AuthenticationSecurityPolicy = None  # type: ignore[assignment]
    limiter: DurableIdentityRateLimiter = None  # type: ignore[assignment]
    audit: EnterpriseAuditLog = None  # type: ignore[assignment]
    oauth: HostedOAuthService = field(init=False)
    four_eyes: IdentityFourEyesService = field(init=False)

    def __post_init__(self) -> None:
        if self.policy is None:
            self.policy = AuthenticationSecurityPolicy()
        if self.limiter is None:
            self.limiter = DurableIdentityRateLimiter(self.engine)
        if self.audit is None:
            self.audit = EnterpriseAuditLog(self.engine)
        self.oauth = HostedOAuthService(self.engine)
        self.four_eyes = IdentityFourEyesService(self.engine)

    def _raw_id_token_permitted(self) -> bool:
        import os

        from responsibleai.dashboard.config import is_production_environment

        env = os.environ.get("WHITEPACT_ENV") or os.environ.get("RAI_ENV") or "development"
        if is_production_environment(env):
            return False
        return bool(self.allow_raw_id_token)

    async def _notify(
        self,
        event_type: str,
        *,
        user_id: str | None = None,
        org_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        safe = {
            k: v
            for k, v in (payload or {}).items()
            if "secret" not in k.lower() and "token" not in k.lower()
        }
        async with self.engine.raw.begin() as conn:
            await conn.execute(
                insert(identity_security_notifications).values(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    org_id=org_id,
                    event_type=event_type,
                    created_at=_iso(),
                    payload_json=json.dumps(safe),
                )
            )
        await self.audit.record(
            action=event_type,
            actor_type="human",
            actor_id=user_id or "system",
            target_type="identity_security",
            result="emitted",
            org_id=org_id,
            metadata=safe,
        )

    async def _org_policy(self, org_id: str | None) -> OrgAuthPolicy:
        if not org_id:
            return OrgAuthPolicy()
        async with self.engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(org_security_policies).where(org_security_policies.c.org_id == org_id)
                )
            ).fetchone()
            sso = (
                await conn.execute(
                    select(organization_sso_configs).where(
                        organization_sso_configs.c.org_id == org_id
                    )
                )
            ).fetchone()
        if row is None and sso is None:
            return OrgAuthPolicy()
        roles = json.loads(row.privileged_roles_json) if row else ["OWNER", "SECURITY_ADMIN"]
        dual = (
            json.loads(row.dual_control_json)
            if row and row.dual_control_json
            else list(DEFAULT_DUAL_CONTROL_ACTIONS)
        )
        if not dual:
            dual = list(DEFAULT_DUAL_CONTROL_ACTIONS)
        return OrgAuthPolicy(
            phishing_resistant_required=bool(row.phishing_resistant_required) if row else False,
            privileged_roles=tuple(roles),
            sso_enforcement=(
                sso.enforcement
                if sso is not None
                else (row.sso_enforcement if row else "SSO_OPTIONAL")
            ),
            dual_control_actions=tuple(dual),
            break_glass_user_id=row.break_glass_user_id if row else None,
            sso_provisioning=sso.provisioning if sso is not None else "INVITE_ONLY",
        )

    async def consume_replay(self, kind: str, replay_key: str) -> None:
        try:
            async with self.engine.raw.begin() as conn:
                await conn.execute(
                    insert(auth_replay_records).values(
                        id=str(uuid.uuid4()),
                        kind=kind,
                        replay_key=replay_key[:128],
                        created_at=_iso(),
                    )
                )
        except IntegrityError as exc:
            raise EnterpriseError(CHALLENGE_REPLAY, "Replay denied.", 401) from exc

    async def begin_webauthn(
        self,
        *,
        user_id: str | None,
        session_id: str | None,
        ceremony: str,
        org_id: str | None = None,
    ) -> dict[str, str]:
        if ceremony not in {"register", "authenticate"}:
            raise forbidden(WEBAUTHN_INVALID, "Unknown ceremony.")
        if ceremony == "register" and not user_id:
            raise unauthenticated()
        challenge = secrets.token_bytes(32)
        challenge_b64 = b64url_encode(challenge)
        async with self.engine.raw.begin() as conn:
            await conn.execute(
                insert(webauthn_challenges).values(
                    challenge_hash=_sha256_bytes(challenge),
                    user_id=user_id,
                    session_id=session_id,
                    org_id=org_id,
                    ceremony=ceremony,
                    rp_id=self.rp_id,
                    origin=self.origin,
                    created_at=_iso(),
                    expires_at=_iso(_now() + timedelta(seconds=_CHALLENGE_TTL)),
                    consumed_at=None,
                )
            )
        return {
            "challenge": challenge_b64,
            "rpId": self.rp_id,
            "origin": self.origin,
            "timeoutMs": str(_CHALLENGE_TTL * 1000),
            "userVerification": "required",
            "ceremony": ceremony,
        }

    async def _consume_challenge(
        self, conn: Any, *, challenge_b64: str, ceremony: str, user_id: str | None
    ) -> bytes:
        raw = b64url_decode(challenge_b64)
        digest = _sha256_bytes(raw)
        row = (
            await conn.execute(
                select(webauthn_challenges).where(webauthn_challenges.c.challenge_hash == digest)
            )
        ).fetchone()
        if row is None:
            raise EnterpriseError(CHALLENGE_REPLAY, "Unknown challenge.", 401)
        now = _iso()
        if row.consumed_at is not None or now >= row.expires_at:
            raise EnterpriseError(CHALLENGE_REPLAY, "Challenge expired or reused.", 401)
        if row.ceremony != ceremony:
            raise forbidden(WEBAUTHN_INVALID, "Ceremony type mismatch.")
        if row.origin != self.origin or row.rp_id != self.rp_id:
            raise forbidden(WEBAUTHN_INVALID, "RP ID or origin mismatch.")
        if ceremony == "register" and row.user_id != user_id:
            raise forbidden(WEBAUTHN_INVALID, "Challenge is bound to another user.")
        if ceremony == "authenticate" and row.user_id and user_id and row.user_id != user_id:
            raise forbidden(WEBAUTHN_INVALID, "Challenge cannot be reused across accounts.")
        result = await conn.execute(
            update(webauthn_challenges)
            .where(
                webauthn_challenges.c.challenge_hash == digest,
                webauthn_challenges.c.consumed_at.is_(None),
            )
            .values(consumed_at=now)
        )
        if (result.rowcount or 0) != 1:
            raise EnterpriseError(CHALLENGE_REPLAY, "Challenge already consumed.", 401)
        return raw

    async def finish_passkey_registration(
        self,
        *,
        user_id: str,
        session: SessionAssurance,
        client_data_b64: str,
        authenticator_data_b64: str,
        display_name: str = "Passkey",
        transports: list[str] | None = None,
        grant: str | None = None,
    ) -> dict[str, Any]:
        if session.user_id != user_id:
            raise unauthenticated()
        await self.require_step_up(
            session, SensitiveAction.ADD_PASSKEY, org_id=session.org_id, grant=grant
        )
        try:
            async with self.engine.raw.begin() as conn:
                challenge = parse_client_data_challenge(client_data_b64)
                await self._consume_challenge(
                    conn, challenge_b64=challenge, ceremony="register", user_id=user_id
                )
                cred_id, public_key, sign_count, flags = verify_registration(
                    client_data_b64=client_data_b64,
                    authenticator_data_b64=authenticator_data_b64,
                    expected_origin=self.origin,
                    expected_rp_id=self.rp_id,
                    expected_challenge=b64url_decode(challenge),
                    require_uv=True,
                )
                cred_id_b64 = b64url_encode(cred_id)
                record_id = str(uuid.uuid4())
                await conn.execute(
                    insert(passkey_credentials).values(
                        id=record_id,
                        user_id=user_id,
                        credential_id=cred_id_b64,
                        public_key=b64url_encode(public_key),
                        sign_count=sign_count,
                        rp_id=self.rp_id,
                        transports_json=json.dumps(transports or []),
                        display_name=display_name[:200],
                        status="ACTIVE",
                        created_at=_iso(),
                        backup_eligible=1 if flags & 0x08 else 0,
                    )
                )
        except IntegrityError as exc:
            raise forbidden(WEBAUTHN_INVALID, "Duplicate credential.") from exc
        except ValueError as exc:
            raise forbidden(WEBAUTHN_INVALID, str(exc)) from exc
        await self._notify("passkey_added", user_id=user_id)
        return {
            "id": record_id,
            "credential_id": cred_id_b64,
            "display_name": display_name,
            "code": "OK",
        }

    async def authenticate_passkey(
        self,
        *,
        client_data_b64: str,
        authenticator_data_b64: str,
        signature_b64: str,
        credential_id: str,
        expected_user_id: str | None = None,
    ) -> tuple[str, str, SessionAssurance]:
        await self.limiter.check(f"passkey:{credential_id}", limit=20, window_seconds=60)
        try:
            async with self.engine.raw.begin() as conn:
                challenge = parse_client_data_challenge(client_data_b64)
                cred = (
                    await conn.execute(
                        select(passkey_credentials).where(
                            passkey_credentials.c.credential_id == credential_id,
                            passkey_credentials.c.status == "ACTIVE",
                            passkey_credentials.c.rp_id == self.rp_id,
                        )
                    )
                ).fetchone()
                if cred is None:
                    raise forbidden(WEBAUTHN_INVALID, "Unknown or removed credential.")
                user = (
                    await conn.execute(select(web_users).where(web_users.c.id == cred.user_id))
                ).fetchone()
                if user is None or user.disabled or user.verification_status == "SUSPENDED":
                    raise unauthenticated("Account is not usable.")
                if expected_user_id and cred.user_id != expected_user_id:
                    raise forbidden(WEBAUTHN_INVALID, "Credential is bound to another user.")
                raw_challenge = await self._consume_challenge(
                    conn, challenge_b64=challenge, ceremony="authenticate", user_id=cred.user_id
                )
                previous = int(cred.sign_count or 0)
                sign_count = verify_assertion(
                    client_data_b64=client_data_b64,
                    authenticator_data_b64=authenticator_data_b64,
                    signature_b64=signature_b64,
                    public_key_uncompressed=b64url_decode(cred.public_key),
                    expected_type="webauthn.get",
                    expected_origin=self.origin,
                    expected_rp_id=self.rp_id,
                    expected_challenge=raw_challenge,
                    require_uv=True,
                    previous_sign_count=previous,
                )
                if sign_count == 0 and previous == 0:
                    await conn.execute(
                        update(passkey_credentials)
                        .where(
                            passkey_credentials.c.id == cred.id,
                            passkey_credentials.c.sign_count == 0,
                        )
                        .values(last_used_at=_iso())
                    )
                else:
                    counter_result = await conn.execute(
                        update(passkey_credentials)
                        .where(
                            passkey_credentials.c.id == cred.id,
                            passkey_credentials.c.sign_count < sign_count,
                        )
                        .values(sign_count=sign_count, last_used_at=_iso())
                    )
                    if (counter_result.rowcount or 0) != 1:
                        raise forbidden(WEBAUTHN_INVALID, "Passkey sign counter did not advance.")
                user_id = cred.user_id
        except ValueError as exc:
            raise forbidden(WEBAUTHN_INVALID, str(exc)) from exc
        token, csrf, assurance = await self.issue_session(
            user_id=user_id,
            methods=(AuthMethod.PASSKEY_UV,),
            ip_label=None,
            user_agent=None,
        )
        await self._notify("passkey_used", user_id=user_id)
        return token, csrf, assurance

    async def list_passkeys(self, user_id: str) -> list[dict[str, Any]]:
        async with self.engine.raw.connect() as conn:
            rows = (
                await conn.execute(
                    select(passkey_credentials).where(
                        passkey_credentials.c.user_id == user_id,
                        passkey_credentials.c.status == "ACTIVE",
                    )
                )
            ).fetchall()
        return [
            {
                "id": row.id,
                "display_name": row.display_name,
                "created_at": row.created_at,
                "last_used_at": row.last_used_at,
                "transports": json.loads(row.transports_json or "[]"),
                "backup_eligible": bool(row.backup_eligible),
            }
            for row in rows
        ]

    async def remove_passkey(
        self,
        *,
        user_id: str,
        credential_row_id: str,
        session: SessionAssurance,
        grant: str | None = None,
    ) -> None:
        await self.require_step_up(
            session, SensitiveAction.REMOVE_PASSKEY, org_id=session.org_id, grant=grant
        )
        async with self.engine.raw.begin() as conn:
            remaining = (
                await conn.execute(
                    select(passkey_credentials).where(
                        passkey_credentials.c.user_id == user_id,
                        passkey_credentials.c.status == "ACTIVE",
                    )
                )
            ).fetchall()
            totp = (
                await conn.execute(
                    select(human_totp_factors).where(human_totp_factors.c.user_id == user_id)
                )
            ).fetchone()
            if len(remaining) <= 1 and (totp is None or totp.status != "ACTIVE"):
                org = await self._org_policy(session.org_id)
                if org.phishing_resistant_required:
                    raise EnterpriseError(
                        LAST_AUTH_METHOD, "Cannot remove the last strong factor.", 403
                    )
            result = await conn.execute(
                update(passkey_credentials)
                .where(
                    passkey_credentials.c.id == credential_row_id,
                    passkey_credentials.c.user_id == user_id,
                    passkey_credentials.c.status == "ACTIVE",
                )
                .values(status="REMOVED")
            )
            if (result.rowcount or 0) != 1:
                raise forbidden(WEBAUTHN_INVALID, "Credential not found.")
        await self._notify("passkey_removed", user_id=user_id)

    async def start_totp(self, user_id: str) -> dict[str, str]:
        secret = mfa.generate_secret()
        uri = mfa.provisioning_uri(secret, account_name=user_id, issuer="WhitePact")
        async with self.engine.raw.begin() as conn:
            existing = (
                await conn.execute(
                    select(human_totp_factors).where(human_totp_factors.c.user_id == user_id)
                )
            ).fetchone()
            if existing is None:
                await conn.execute(
                    insert(human_totp_factors).values(
                        user_id=user_id,
                        secret_encrypted="",
                        pending_secret_encrypted=secret,
                        status="PENDING",
                        created_at=_iso(),
                    )
                )
            else:
                await conn.execute(
                    update(human_totp_factors)
                    .where(human_totp_factors.c.user_id == user_id)
                    .values(
                        pending_secret_encrypted=secret,
                        status="PENDING" if existing.status != "ACTIVE" else existing.status,
                    )
                )
        return {"otpauth_uri": uri, "status": "PENDING"}

    async def confirm_totp(self, user_id: str, code: str) -> None:
        await self.limiter.check(f"totp:{user_id}", limit=8, window_seconds=60)
        async with self.engine.raw.begin() as conn:
            row = (
                await conn.execute(
                    select(human_totp_factors).where(human_totp_factors.c.user_id == user_id)
                )
            ).fetchone()
            if row is None or not row.pending_secret_encrypted:
                raise forbidden(MFA_REQUIRED, "No TOTP enrollment in progress.")
            if not mfa.verify_code(row.pending_secret_encrypted, code):
                await conn.execute(
                    update(human_totp_factors)
                    .where(human_totp_factors.c.user_id == user_id)
                    .values(failed_attempts=int(row.failed_attempts or 0) + 1)
                )
                raise forbidden(AUTHENTICATION_FAILED, "Invalid authenticator code.")
            timestep = int(time.time()) // 30
            await conn.execute(
                update(human_totp_factors)
                .where(human_totp_factors.c.user_id == user_id)
                .values(
                    secret_encrypted=row.pending_secret_encrypted,
                    pending_secret_encrypted=None,
                    status="ACTIVE",
                    confirmed_at=_iso(),
                    last_timestep=timestep,
                    failed_attempts=0,
                )
            )
        await self._notify("totp_added", user_id=user_id)

    async def verify_totp(self, user_id: str, code: str) -> None:
        await self.limiter.check(f"totp:{user_id}", limit=8, window_seconds=60)
        async with self.engine.raw.begin() as conn:
            row = (
                await conn.execute(
                    select(human_totp_factors).where(human_totp_factors.c.user_id == user_id)
                )
            ).fetchone()
            if row is None or row.status != "ACTIVE":
                raise forbidden(MFA_REQUIRED, "TOTP is not enrolled.")
            timestep = int(time.time()) // 30
            if row.last_timestep is not None and abs(timestep - int(row.last_timestep)) == 0:
                if hmac.compare_digest(str(row.last_timestep), str(timestep)):
                    raise forbidden(CHALLENGE_REPLAY, "TOTP code already used.")
            if not mfa.verify_code(row.secret_encrypted, code):
                raise forbidden(AUTHENTICATION_FAILED, "Invalid authenticator code.")
            await conn.execute(
                update(human_totp_factors)
                .where(human_totp_factors.c.user_id == user_id)
                .values(last_timestep=timestep, failed_attempts=0)
            )

    async def remove_totp(
        self, *, user_id: str, session: SessionAssurance, grant: str | None = None
    ) -> None:
        await self.require_step_up(
            session, SensitiveAction.DISABLE_MFA, org_id=session.org_id, grant=grant
        )
        async with self.engine.raw.begin() as conn:
            keys = (
                await conn.execute(
                    select(passkey_credentials).where(
                        passkey_credentials.c.user_id == user_id,
                        passkey_credentials.c.status == "ACTIVE",
                    )
                )
            ).fetchall()
            org = await self._org_policy(session.org_id)
            if not keys and org.phishing_resistant_required:
                raise EnterpriseError(
                    SECURITY_DOWNGRADE_BLOCKED, "Cannot disable the last strong factor.", 403
                )
            await conn.execute(
                update(human_totp_factors)
                .where(human_totp_factors.c.user_id == user_id)
                .values(status="REMOVED")
            )
        await self._notify("totp_removed", user_id=user_id)

    async def issue_recovery_codes(
        self, user_id: str, *, session: SessionAssurance, grant: str | None = None
    ) -> list[str]:
        await self.require_step_up(
            session, SensitiveAction.CHANGE_RECOVERY_METHODS, org_id=session.org_id, grant=grant
        )
        codes = [
            "".join(secrets.choice(_ALPHABET) for _ in range(_CODE_LEN))
            for _ in range(_RECOVERY_CODES)
        ]
        async with self.engine.raw.begin() as conn:
            current = (
                await conn.execute(
                    select(recovery_code_hashes.c.generation)
                    .where(recovery_code_hashes.c.user_id == user_id)
                    .order_by(recovery_code_hashes.c.generation.desc())
                    .limit(1)
                )
            ).fetchone()
            generation = int(current[0]) + 1 if current else 1
            await conn.execute(
                update(recovery_code_hashes)
                .where(
                    recovery_code_hashes.c.user_id == user_id,
                    recovery_code_hashes.c.consumed_at.is_(None),
                )
                .values(consumed_at=_iso())
            )
            for code in codes:
                await conn.execute(
                    insert(recovery_code_hashes).values(
                        id=str(uuid.uuid4()),
                        user_id=user_id,
                        code_hash=_hash(code),
                        generation=generation,
                        created_at=_iso(),
                    )
                )
        await self._notify("recovery_codes_regenerated", user_id=user_id)
        return codes

    async def consume_recovery_code(self, user_id: str, code: str) -> None:
        await self.limiter.check(f"recovery-code:{user_id}", limit=5, window_seconds=300)
        async with self.engine.raw.begin() as conn:
            row = (
                await conn.execute(
                    select(recovery_code_hashes).where(
                        recovery_code_hashes.c.user_id == user_id,
                        recovery_code_hashes.c.code_hash == _hash(code.strip().upper()),
                        recovery_code_hashes.c.consumed_at.is_(None),
                    )
                )
            ).fetchone()
            if row is None:
                raise forbidden(AUTHENTICATION_FAILED, "Invalid recovery code.")
            result = await conn.execute(
                update(recovery_code_hashes)
                .where(
                    recovery_code_hashes.c.id == row.id,
                    recovery_code_hashes.c.consumed_at.is_(None),
                )
                .values(consumed_at=_iso())
            )
            if (result.rowcount or 0) != 1:
                raise EnterpriseError(CHALLENGE_REPLAY, "Recovery code already used.", 401)
        await self._notify("recovery_code_used", user_id=user_id)

    async def issue_session(
        self,
        *,
        user_id: str,
        methods: tuple[str, ...],
        org_id: str | None = None,
        ip_label: str | None,
        user_agent: str | None,
        rotate_from: str | None = None,
        amr: tuple[str, ...] = (),
        acr: str | None = None,
        authn_context: str | None = None,
        webauthn_uv: bool | None = None,
        webauthn_backup_eligible: bool | None = None,
    ) -> tuple[str, str, SessionAssurance]:
        if PRODUCTION_GATE_B_OPEN:
            raise RuntimeError("identity security must not open Gate B")
        token = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        session_id = str(uuid.uuid4())
        now = _now()
        evidence = map_authentication_assurance(
            methods=tuple(str(m) for m in methods),
            amr=amr,
            acr=acr,
            authn_context=authn_context,
            webauthn_uv=webauthn_uv
            if webauthn_uv is not None
            else (AuthMethod.PASSKEY_UV in methods),
            webauthn_backup_eligible=webauthn_backup_eligible,
        )
        level = SESSION_LEVEL.get(evidence.level, evidence.level)
        phishing = evidence.phishing_resistant
        async with self.engine.raw.begin() as conn:
            if rotate_from:
                await conn.execute(
                    update(web_sessions)
                    .where(web_sessions.c.token_hash == _hash(rotate_from))
                    .values(revoked=1)
                )
            await conn.execute(
                insert(web_sessions).values(
                    token_hash=_hash(token),
                    session_id=session_id,
                    user_id=user_id,
                    org_id=org_id,
                    csrf_hash=_hash(csrf),
                    created_at=_iso(now),
                    expires_at=_iso(now + timedelta(hours=_SESSION_ABSOLUTE_HOURS)),
                    last_seen_at=_iso(now),
                    revoked=0,
                    assurance_level=level,
                    auth_methods_json=json.dumps(list(methods)),
                    auth_time=_iso(now),
                    phishing_resistant=1 if phishing else 0,
                    ip_label=ip_label,
                    user_agent=(user_agent or "")[:512],
                    inactivity_expires_at=_iso(now + timedelta(hours=_SESSION_IDLE_HOURS)),
                    rotated_from=_hash(rotate_from) if rotate_from else None,
                )
            )
        assurance = SessionAssurance(
            level=level,
            methods=methods,
            auth_time=_iso(now),
            phishing_resistant=phishing,
            session_id=session_id,
            user_id=user_id,
            org_id=org_id,
        )
        return token, csrf, assurance

    async def load_session(self, raw_token: str) -> tuple[str, str, SessionAssurance]:
        token, _, csrf = raw_token.partition(".")
        if not token:
            token = raw_token
        now = _now()
        async with self.engine.raw.begin() as conn:
            row = (
                await conn.execute(
                    select(web_sessions).where(
                        web_sessions.c.token_hash == _hash(token),
                        web_sessions.c.revoked == 0,
                    )
                )
            ).fetchone()
            if row is None:
                raise unauthenticated()
            if _iso(now) >= row.expires_at:
                raise unauthenticated()
            idle = getattr(row, "inactivity_expires_at", None)
            if idle and _iso(now) >= idle:
                raise unauthenticated()
            user = (
                await conn.execute(select(web_users).where(web_users.c.id == row.user_id))
            ).fetchone()
            if user is None or user.disabled or user.verification_status == "SUSPENDED":
                raise unauthenticated()
            if row.org_id:
                membership = (
                    await conn.execute(
                        select(web_memberships).where(
                            web_memberships.c.user_id == row.user_id,
                            web_memberships.c.org_id == row.org_id,
                        )
                    )
                ).fetchone()
                org = (
                    await conn.execute(
                        select(organizations).where(organizations.c.id == row.org_id)
                    )
                ).fetchone()
                if membership is None or getattr(membership, "status", "ACTIVE") != "ACTIVE":
                    raise unauthenticated()
                if org is None or getattr(org, "governance_status", "ACTIVE") in {
                    "DISABLED",
                    "SUSPENDED",
                }:
                    raise unauthenticated()
            await conn.execute(
                update(web_sessions)
                .where(web_sessions.c.token_hash == row.token_hash)
                .values(
                    last_seen_at=_iso(now),
                    inactivity_expires_at=_iso(now + timedelta(hours=_SESSION_IDLE_HOURS)),
                )
            )
            session_id = row.session_id or row.token_hash
            methods = tuple(
                json.loads(getattr(row, "auth_methods_json", None) or "[]") or ["PASSWORD"]
            )
            assurance = SessionAssurance(
                level=getattr(row, "assurance_level", None) or "PASSWORD",
                methods=methods,
                auth_time=getattr(row, "auth_time", None) or row.created_at,
                phishing_resistant=bool(getattr(row, "phishing_resistant", 0)),
                session_id=session_id,
                user_id=row.user_id,
                org_id=row.org_id,
                step_up_expires_at=getattr(row, "last_step_up_at", None),
            )
        return token, csrf, assurance

    async def list_sessions(self, user_id: str) -> list[dict[str, Any]]:
        async with self.engine.raw.connect() as conn:
            rows = (
                await conn.execute(select(web_sessions).where(web_sessions.c.user_id == user_id))
            ).fetchall()
        return [
            {
                "session_id": row.session_id,
                "created_at": row.created_at,
                "last_used_at": row.last_seen_at,
                "ip_label": getattr(row, "ip_label", None),
                "user_agent": getattr(row, "user_agent", None),
                "assurance_level": getattr(row, "assurance_level", None),
                "auth_methods": json.loads(getattr(row, "auth_methods_json", None) or "[]"),
                "revoked": bool(row.revoked),
                "last_step_up_at": getattr(row, "last_step_up_at", None),
            }
            for row in rows
        ]

    async def revoke_session(self, *, user_id: str, session_id: str) -> None:
        async with self.engine.raw.begin() as conn:
            await conn.execute(
                update(web_sessions)
                .where(web_sessions.c.user_id == user_id, web_sessions.c.session_id == session_id)
                .values(revoked=1)
            )
        await self._notify("session_revoked", user_id=user_id)

    async def revoke_all_sessions(self, user_id: str) -> int:
        async with self.engine.raw.begin() as conn:
            result = await conn.execute(
                update(web_sessions)
                .where(web_sessions.c.user_id == user_id, web_sessions.c.revoked == 0)
                .values(revoked=1)
            )
        await self._notify("logout_all", user_id=user_id)
        return result.rowcount or 0

    async def issue_step_up(
        self, session: SessionAssurance, action: SensitiveAction | str, *, org_id: str | None
    ) -> str:
        grant = secrets.token_urlsafe(32)
        org = await self._org_policy(org_id or session.org_id)
        required = self.policy.required_assurance_for(action, role=None, org=org)
        async with self.engine.raw.begin() as conn:
            await conn.execute(
                insert(step_up_grants).values(
                    id=str(uuid.uuid4()),
                    grant_hash=_hash(grant),
                    user_id=session.user_id,
                    session_id=session.session_id,
                    action=str(action),
                    org_id=org_id or session.org_id,
                    assurance_required=required,
                    created_at=_iso(),
                    expires_at=_iso(_now() + timedelta(seconds=_STEP_UP_TTL)),
                )
            )
        return grant

    async def consume_step_up(
        self, session: SessionAssurance, action: SensitiveAction | str, grant: str
    ) -> None:
        async with self.engine.raw.begin() as conn:
            row = (
                await conn.execute(
                    select(step_up_grants).where(step_up_grants.c.grant_hash == _hash(grant))
                )
            ).fetchone()
            if row is None:
                raise EnterpriseError(STEP_UP_REQUIRED, "Step-up grant is missing.", 401)
            now = _iso()
            if row.consumed_at or now >= row.expires_at:
                raise EnterpriseError(STEP_UP_REQUIRED, "Step-up grant expired or reused.", 401)
            if row.action != str(action):
                raise EnterpriseError(
                    STEP_UP_REQUIRED, "Step-up grant is bound to a different action.", 401
                )
            if row.user_id != session.user_id or row.session_id != session.session_id:
                raise EnterpriseError(
                    STEP_UP_REQUIRED, "Step-up grant is bound to another session.", 401
                )
            if session.rank() < ASSURANCE_RANK.get(row.assurance_required, 0):
                raise EnterpriseError(
                    "AUTHENTICATION_ASSURANCE_TOO_LOW", "Assurance too low for this action.", 403
                )
            result = await conn.execute(
                update(step_up_grants)
                .where(step_up_grants.c.id == row.id, step_up_grants.c.consumed_at.is_(None))
                .values(consumed_at=now)
            )
            if (result.rowcount or 0) != 1:
                raise EnterpriseError(CHALLENGE_REPLAY, "Step-up grant already consumed.", 401)
            await conn.execute(
                update(web_sessions)
                .where(web_sessions.c.session_id == session.session_id)
                .values(last_step_up_at=now)
            )

    async def require_step_up(
        self,
        session: SessionAssurance,
        action: SensitiveAction | str,
        *,
        org_id: str | None,
        grant: str | None = None,
    ) -> None:
        if not grant:
            issued = await self.issue_step_up(session, action, org_id=org_id)
            raise EnterpriseError(
                STEP_UP_REQUIRED, f"Fresh step-up authentication is required:{issued}", 401
            )
        await self.consume_step_up(session, action, grant)

    async def authenticate_password(
        self, email: str, password: str, *, org_id: str | None = None
    ) -> tuple[str, str, SessionAssurance] | None:
        await self.limiter.check(f"login:{email.casefold()}", limit=10, window_seconds=60)
        from responsibleai.db.web_identity_repository import WebIdentityRepository

        repo = WebIdentityRepository(self.engine)
        identity = await repo.authenticate(email, password)
        if identity is None:
            return None
        user_id, _email, _name = identity
        resolved_org = org_id or await repo.primary_org_id(user_id)
        org_policy = await self._org_policy(resolved_org)
        role = None
        if resolved_org:
            async with self.engine.raw.connect() as conn:
                membership = (
                    await conn.execute(
                        select(web_memberships).where(
                            web_memberships.c.user_id == user_id,
                            web_memberships.c.org_id == resolved_org,
                        )
                    )
                ).fetchone()
                if membership is not None:
                    role = membership.role
        decision = self.policy.evaluate_login(
            methods=(AuthMethod.PASSWORD,), role=role, org=org_policy
        )
        if not decision.allowed:
            raise EnterpriseError(decision.code, "Authentication policy denied this login.", 403)
        token, csrf, assurance = await self.issue_session(
            user_id=user_id,
            methods=(AuthMethod.PASSWORD,),
            org_id=resolved_org,
            ip_label=None,
            user_agent=None,
        )
        return token, csrf, assurance

    async def google_login(
        self, *, id_token: str, nonce: str, intended_org_id: str | None = None
    ) -> dict[str, Any]:
        if not self._raw_id_token_permitted():
            raise forbidden(
                PROVIDER_TOKEN_INVALID,
                "Hosted Google login requires the authorization-code + PKCE callback.",
            )
        if not self.google_client_id:
            raise forbidden(PROVIDER_TOKEN_INVALID, "Google Sign-In is not configured.")
        await self.limiter.check("oauth:google", limit=20, window_seconds=60)
        validator = OIDCTokenValidator(
            issuer="https://accounts.google.com",
            audience=self.google_client_id,
            jwks_url=self.google_jwks_url,
        )
        claims = await validator.validate(id_token, expected_nonce=nonce)
        if claims.issuer.rstrip("/") not in GOOGLE_ISSUERS and claims.issuer not in GOOGLE_ISSUERS:
            raise forbidden(PROVIDER_TOKEN_INVALID, "Unexpected Google issuer.")
        kind = "WORKSPACE" if claims.hosted_domain else "PERSONAL"
        if intended_org_id:
            binding = await self._binding(intended_org_id, GOOGLE_WORKSPACE)
            if binding is None:
                raise EnterpriseError(
                    COMPANY_VERIFICATION_REQUIRED,
                    "Organization is not bound to Google Workspace.",
                    403,
                )
            if kind != "WORKSPACE":
                raise EnterpriseError(
                    GOOGLE_WORKSPACE_MISMATCH,
                    "Personal Google accounts cannot join via company path.",
                    403,
                )
            if claims.hosted_domain != binding["verified_domain"]:
                raise EnterpriseError(
                    GOOGLE_WORKSPACE_MISMATCH,
                    "Google hosted domain does not match the bound organization.",
                    403,
                )
            return await self._complete_provider_login(
                provider=GOOGLE_PROVIDER,
                claims=claims,
                account_kind=kind,
                org_id=intended_org_id,
                method=AuthMethod.GOOGLE_OIDC,
            )
        return await self._complete_provider_login(
            provider=GOOGLE_PROVIDER,
            claims=claims,
            account_kind=kind,
            org_id=None,
            method=AuthMethod.GOOGLE_OIDC,
        )

    async def microsoft_login(
        self, *, id_token: str, nonce: str, intended_org_id: str | None = None
    ) -> dict[str, Any]:
        if not self._raw_id_token_permitted():
            raise forbidden(
                PROVIDER_TOKEN_INVALID,
                "Hosted Microsoft login requires the authorization-code + PKCE callback.",
            )
        if not self.microsoft_client_id:
            raise forbidden(PROVIDER_TOKEN_INVALID, "Microsoft Sign-In is not configured.")
        await self.limiter.check("oauth:microsoft", limit=20, window_seconds=60)
        validator = OIDCTokenValidator(
            issuer="https://login.microsoftonline.com/common/v2.0",
            audience=self.microsoft_client_id,
            jwks_url=self.microsoft_jwks_url or MICROSOFT_JWKS,
            strict_issuer=False,
            allowed_issuer_hosts=frozenset({"login.microsoftonline.com"}),
        )
        claims = await validator.validate(id_token, expected_nonce=nonce)
        if "login.microsoftonline.com" not in claims.issuer:
            raise forbidden(PROVIDER_TOKEN_INVALID, "Unexpected Microsoft issuer.")
        tenant = claims.tenant_id
        kind = "PERSONAL" if tenant == MSA_TENANT else "ORGANIZATIONAL"
        if intended_org_id:
            binding = await self._binding(intended_org_id, ENTRA_PROVIDER)
            if binding is None:
                raise EnterpriseError(
                    COMPANY_VERIFICATION_REQUIRED, "Organization is not bound to Entra.", 403
                )
            if kind == "PERSONAL":
                raise EnterpriseError(
                    ENTRA_TENANT_MISMATCH,
                    "Personal Microsoft accounts cannot use the organization path.",
                    403,
                )
            if tenant != binding["tenant_id"]:
                raise EnterpriseError(
                    ENTRA_TENANT_MISMATCH,
                    "Entra tenant does not match the bound organization.",
                    403,
                )
            return await self._complete_provider_login(
                provider=MICROSOFT_PROVIDER,
                claims=claims,
                account_kind=kind,
                org_id=intended_org_id,
                method=AuthMethod.MICROSOFT_OIDC,
            )
        return await self._complete_provider_login(
            provider=MICROSOFT_PROVIDER,
            claims=claims,
            account_kind=kind,
            org_id=None,
            method=AuthMethod.MICROSOFT_OIDC,
        )

    async def begin_hosted_oauth(
        self,
        *,
        provider: str,
        redirect_uri: str | None = None,
        intended_org_id: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, str]:
        await self.limiter.check(f"oauth:{provider.casefold()}", limit=20, window_seconds=60)
        canonical = canonicalize_provider(provider)
        if canonical == "GOOGLE":
            if not self.google_client_id or not self.google_client_secret:
                raise forbidden(PROVIDER_TOKEN_INVALID, "Google Sign-In is not configured.")
            client_id = self.google_client_id
        elif canonical == "MICROSOFT":
            if not self.microsoft_client_id or not self.microsoft_client_secret:
                raise forbidden(PROVIDER_TOKEN_INVALID, "Microsoft Sign-In is not configured.")
            client_id = self.microsoft_client_id
        else:
            raise forbidden(PROVIDER_TOKEN_INVALID, "Unknown hosted identity provider.")
        return await self.oauth.begin(
            provider=canonical,
            redirect_uri=redirect_uri or self.hosted_redirect_uri,
            client_id=client_id,
            intended_org_id=intended_org_id,
            session_id=session_id,
        )

    async def complete_hosted_oauth(
        self,
        *,
        provider: str,
        state: str,
        code: str,
        redirect_uri: str | None = None,
    ) -> dict[str, Any]:
        await self.limiter.check(
            f"oauth:{provider.casefold()}:callback", limit=20, window_seconds=60
        )
        canonical = canonicalize_provider(provider)
        callback = redirect_uri or self.hosted_redirect_uri
        if canonical == "GOOGLE":
            claims, txn = await self.oauth.consume_and_validate_callback(
                provider="GOOGLE",
                state=state,
                code=code,
                redirect_uri=callback,
                client_id=self.google_client_id,
                client_secret=self.google_client_secret,
                jwks_url=self.google_jwks_url,
                issuer=GOOGLE_ISSUER,
            )
            kind = "WORKSPACE" if claims.hosted_domain else "PERSONAL"
            method = AuthMethod.GOOGLE_OIDC
            login_provider = GOOGLE_PROVIDER
        elif canonical == "MICROSOFT":
            claims, txn = await self.oauth.consume_and_validate_callback(
                provider="MICROSOFT",
                state=state,
                code=code,
                redirect_uri=callback,
                client_id=self.microsoft_client_id,
                client_secret=self.microsoft_client_secret,
                jwks_url=self.microsoft_jwks_url or MICROSOFT_JWKS,
                issuer="https://login.microsoftonline.com/common/v2.0",
                microsoft_issuer_hosts=True,
            )
            kind = "PERSONAL" if claims.tenant_id == MSA_TENANT else "ORGANIZATIONAL"
            method = AuthMethod.MICROSOFT_OIDC
            login_provider = MICROSOFT_PROVIDER
        else:
            raise forbidden(PROVIDER_TOKEN_INVALID, "Unknown hosted identity provider.")
        intended = txn.intended_org_id
        if intended:
            if canonical == "GOOGLE":
                binding = await self._binding(intended, GOOGLE_WORKSPACE)
                if binding is None:
                    raise EnterpriseError(
                        COMPANY_VERIFICATION_REQUIRED,
                        "Organization is not bound to Google Workspace.",
                        403,
                    )
                if kind != "WORKSPACE":
                    raise EnterpriseError(
                        GOOGLE_WORKSPACE_MISMATCH,
                        "Personal Google accounts cannot join via company path.",
                        403,
                    )
                if claims.hosted_domain != binding["verified_domain"]:
                    raise EnterpriseError(
                        GOOGLE_WORKSPACE_MISMATCH,
                        "Google hosted domain does not match the bound organization.",
                        403,
                    )
            else:
                binding = await self._binding(intended, ENTRA_PROVIDER)
                if binding is None:
                    raise EnterpriseError(
                        COMPANY_VERIFICATION_REQUIRED, "Organization is not bound to Entra.", 403
                    )
                if kind == "PERSONAL":
                    raise EnterpriseError(
                        ENTRA_TENANT_MISMATCH,
                        "Personal Microsoft accounts cannot use the organization path.",
                        403,
                    )
                if claims.tenant_id != binding["tenant_id"]:
                    raise EnterpriseError(
                        ENTRA_TENANT_MISMATCH,
                        "Entra tenant does not match the bound organization.",
                        403,
                    )
        return await self._complete_provider_login(
            provider=login_provider,
            claims=claims,
            account_kind=kind,
            org_id=intended,
            method=method,
        )

    async def _binding(self, org_id: str, provider: str) -> dict[str, Any] | None:
        async with self.engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(organization_idp_bindings).where(
                        organization_idp_bindings.c.org_id == org_id,
                        organization_idp_bindings.c.provider == provider,
                        organization_idp_bindings.c.status == "ACTIVE",
                    )
                )
            ).fetchone()
        return dict(row._mapping) if row else None

    async def _complete_provider_login(
        self,
        *,
        provider: str,
        claims: VerifiedIDToken,
        account_kind: str,
        org_id: str | None,
        method: str,
    ) -> dict[str, Any]:
        canonical, subject, tenant_key = provider_account_key(
            provider=provider,
            subject=claims.subject,
            tenant_id=claims.tenant_id or claims.hosted_domain,
        )
        async with self.engine.raw.connect() as conn:
            link = (
                await conn.execute(
                    select(provider_identities).where(
                        provider_identities.c.provider == canonical,
                        provider_identities.c.subject == subject,
                        provider_identities.c.tenant_id == tenant_key,
                    )
                )
            ).fetchone()
        if link is None:
            return {
                "status": "UNLINKED_PROVIDER",
                "provider": canonical,
                "account_kind": account_kind,
                "subject": subject,
                "email": claims.email,
            }
        if org_id:
            await self._assert_membership_or_jit(link.user_id, org_id, claims, canonical)
        token, _csrf, assurance = await self.issue_session(
            user_id=link.user_id,
            methods=(method,),
            org_id=org_id,
            ip_label=None,
            user_agent=None,
            amr=getattr(claims, "amr", ()) or (),
            acr=getattr(claims, "acr", None),
        )
        await self._notify(
            "provider_login", user_id=link.user_id, org_id=org_id, payload={"provider": provider}
        )
        return {
            "status": "AUTHENTICATED",
            "session_token": token,
            "assurance": assurance.level,
            "account_kind": account_kind,
        }

    async def _assert_membership(self, user_id: str, org_id: str) -> None:
        async with self.engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(web_memberships).where(
                        web_memberships.c.user_id == user_id,
                        web_memberships.c.org_id == org_id,
                        web_memberships.c.status == "ACTIVE",
                    )
                )
            ).fetchone()
        if row is None:
            raise EnterpriseError(
                SSO_TENANT_MISMATCH, "Provider login does not grant organization membership.", 403
            )

    async def _assert_membership_or_jit(
        self,
        user_id: str,
        org_id: str,
        claims: VerifiedIDToken,
        provider: str,
    ) -> None:
        try:
            await self._assert_membership(user_id, org_id)
            return
        except EnterpriseError as exc:
            if exc.code != SSO_TENANT_MISMATCH:
                raise
        org = await self._org_policy(org_id)
        if org.sso_provisioning != "JIT_OPT_IN":
            raise EnterpriseError(
                SSO_TENANT_MISMATCH, "Provider login does not grant organization membership.", 403
            )
        if provider == GOOGLE_PROVIDER:
            binding = await self._binding(org_id, GOOGLE_WORKSPACE)
            if (
                binding is None
                or not claims.hosted_domain
                or claims.hosted_domain != binding.get("verified_domain")
            ):
                raise EnterpriseError(
                    GOOGLE_WORKSPACE_MISMATCH,
                    "JIT requires an exact verified hosted-domain binding.",
                    403,
                )
        elif provider == MICROSOFT_PROVIDER:
            binding = await self._binding(org_id, ENTRA_PROVIDER)
            if (
                binding is None
                or not claims.tenant_id
                or claims.tenant_id != binding.get("tenant_id")
            ):
                raise EnterpriseError(
                    ENTRA_TENANT_MISMATCH,
                    "JIT requires an exact verified Entra tenant binding.",
                    403,
                )
        else:
            raise EnterpriseError(SSO_TENANT_MISMATCH, "JIT is not enabled for this provider.", 403)
        async with self.engine.raw.connect() as conn:
            verification = (
                await conn.execute(
                    select(organization_verifications).where(
                        organization_verifications.c.org_id == org_id
                    )
                )
            ).fetchone()
        if verification is None or verification.status not in {
            "DOMAIN_VERIFIED",
            "ORGANIZATION_VERIFIED",
        }:
            raise EnterpriseError(
                COMPANY_VERIFICATION_REQUIRED, "JIT requires a verified organization.", 403
            )
        email_suffix = (
            (claims.email or "").rsplit("@", 1)[-1].lower()
            if claims.email and "@" in claims.email
            else ""
        )
        bound_domain = str((binding or {}).get("verified_domain") or "").lower()
        if (
            bound_domain
            and email_suffix
            and email_suffix != bound_domain
            and provider == GOOGLE_PROVIDER
        ):
            # Email suffix is never sufficient; hosted-domain claim already matched.
            pass
        async with self.engine.raw.begin() as conn:
            await conn.execute(
                insert(web_memberships).values(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    org_id=org_id,
                    role="MEMBER",
                    status="ACTIVE",
                    created_at=_iso(),
                    accepted_at=_iso(),
                )
            )

    async def link_provider(
        self,
        *,
        session: SessionAssurance,
        provider: str,
        claims: VerifiedIDToken,
        grant: str | None,
        account_kind: str,
    ) -> None:
        action = (
            SensitiveAction.LINK_GOOGLE
            if canonicalize_provider(provider) == GOOGLE_PROVIDER
            else SensitiveAction.LINK_MICROSOFT
        )
        await self.require_step_up(session, action, org_id=session.org_id, grant=grant)
        canonical, subject, tenant_key = provider_account_key(
            provider=provider,
            subject=claims.subject,
            tenant_id=claims.tenant_id or claims.hosted_domain,
        )
        try:
            async with self.engine.raw.begin() as conn:
                await conn.execute(
                    insert(provider_identities).values(
                        id=str(uuid.uuid4()),
                        user_id=session.user_id,
                        provider=canonical,
                        subject=subject,
                        tenant_id=tenant_key,
                        hosted_domain=claims.hosted_domain,
                        account_kind=account_kind,
                        email_at_link=claims.email,
                        status="ACTIVE",
                        created_at=_iso(),
                    )
                )
        except IntegrityError as exc:
            raise EnterpriseError(
                ACCOUNT_LINK_CONFLICT, "Provider identity is already linked.", 409
            ) from exc
        await self._notify(f"{provider.lower()}_linked", user_id=session.user_id)

    async def bind_organization_idp(
        self,
        *,
        org_id: str,
        provider: str,
        tenant_id: str | None,
        issuer: str,
        verified_domain: str | None,
        configured_by: str,
        session: SessionAssurance,
        grant: str | None,
    ) -> None:
        action = {
            GOOGLE_WORKSPACE: SensitiveAction.CHANGE_GOOGLE_WORKSPACE_BINDING,
            ENTRA_PROVIDER: SensitiveAction.CHANGE_ENTRA_BINDING,
        }.get(provider, SensitiveAction.CONFIGURE_SSO)
        await self.require_step_up(session, action, org_id=org_id, grant=grant)
        async with self.engine.raw.connect() as conn:
            verification = (
                await conn.execute(
                    select(organization_verifications).where(
                        organization_verifications.c.org_id == org_id
                    )
                )
            ).fetchone()
        if verification is None or verification.status not in {
            "DOMAIN_VERIFIED",
            "ORGANIZATION_VERIFIED",
        }:
            raise EnterpriseError(
                COMPANY_VERIFICATION_REQUIRED,
                "Company verification is required before IdP binding.",
                403,
            )
        async with self.engine.raw.begin() as conn:
            await conn.execute(
                insert(organization_idp_bindings).values(
                    id=str(uuid.uuid4()),
                    org_id=org_id,
                    provider=provider,
                    tenant_id=tenant_id,
                    issuer=issuer,
                    verified_domain=verified_domain,
                    status="ACTIVE",
                    configured_by=configured_by,
                    verified_at=_iso(),
                    policy_json="{}",
                    created_at=_iso(),
                )
            )
        await self._notify(
            "idp_binding_changed",
            user_id=configured_by,
            org_id=org_id,
            payload={"provider": provider},
        )

    async def configure_sso(
        self,
        *,
        org_id: str,
        session: SessionAssurance,
        grant: str | None,
        protocol: str,
        issuer: str,
        client_id: str,
        client_secret: str | None,
        redirect_uri: str,
        enforcement: str,
        provisioning: str,
        idp_entity_id: str | None = None,
        idp_sso_url: str | None = None,
        idp_x509_cert: str | None = None,
        discovery_url: str | None = None,
        jwks_url: str | None = None,
        four_eyes_id: str | None = None,
    ) -> None:
        await self.require_step_up(
            session, SensitiveAction.CONFIGURE_SSO, org_id=org_id, grant=grant
        )
        if enforcement == "SSO_OPTIONAL":
            existing = await self._org_policy(org_id)
            if existing.sso_enforcement == "SSO_REQUIRED":
                params = {
                    "org_id": org_id,
                    "protocol": protocol,
                    "issuer": issuer,
                    "client_id": client_id,
                    "redirect_uri": redirect_uri,
                    "enforcement": enforcement,
                    "provisioning": provisioning,
                }
                if not four_eyes_id:
                    raise EnterpriseError(
                        "FOUR_EYES_REQUIRED",
                        "Disabling required SSO needs four-eyes approval.",
                        403,
                    )
                await self.four_eyes.consume(
                    org_id=org_id,
                    request_id=four_eyes_id,
                    action=SensitiveAction.DISABLE_REQUIRED_SSO.value,
                    parameters=params,
                )
        parsed = urlparse(redirect_uri)
        if parsed.scheme not in {"https", "http"} or not parsed.netloc or "*" in redirect_uri:
            raise forbidden("SSO_REQUIRED", "Redirect URI must be pre-registered and exact.")
        if issuer:
            validate_outbound_url(
                issuer if "://" in issuer else f"https://{issuer}", DestinationPolicy.PUBLIC_ONLY
            )
        async with self.engine.raw.begin() as conn:
            await conn.execute(
                insert(organization_sso_configs).values(
                    id=str(uuid.uuid4()),
                    org_id=org_id,
                    protocol=protocol,
                    issuer=issuer,
                    client_id=client_id,
                    client_secret_encrypted=client_secret,
                    discovery_url=discovery_url,
                    jwks_url=jwks_url,
                    redirect_uri=redirect_uri,
                    enforcement=enforcement,
                    provisioning=provisioning
                    if provisioning in {"INVITE_ONLY", "JIT_OPT_IN"}
                    else "INVITE_ONLY",
                    idp_entity_id=idp_entity_id,
                    idp_sso_url=idp_sso_url,
                    idp_x509_cert=idp_x509_cert,
                    created_by=session.user_id,
                    created_at=_iso(),
                    updated_at=_iso(),
                )
            )
        await self._notify("sso_configured", user_id=session.user_id, org_id=org_id)

    async def consume_oidc_code_claims(
        self,
        *,
        org_id: str,
        claims: VerifiedIDToken,
        redirect_uri: str,
    ) -> dict[str, Any]:
        async with self.engine.raw.connect() as conn:
            cfg = (
                await conn.execute(
                    select(organization_sso_configs).where(
                        organization_sso_configs.c.org_id == org_id
                    )
                )
            ).fetchone()
        if cfg is None:
            raise forbidden(SSO_REQUIRED, "SSO is not configured.")
        if redirect_uri != cfg.redirect_uri:
            raise forbidden(PROVIDER_TOKEN_INVALID, "Redirect URI mismatch.")
        if claims.issuer.rstrip("/") != cfg.issuer.rstrip("/"):
            raise forbidden(PROVIDER_TOKEN_INVALID, "IdP mix-up: issuer mismatch.")
        binding = await self._binding(org_id, ENTRA_PROVIDER) or await self._binding(
            org_id, GOOGLE_WORKSPACE
        )
        if (
            binding
            and claims.tenant_id
            and binding.get("tenant_id")
            and claims.tenant_id != binding["tenant_id"]
        ):
            raise EnterpriseError(SSO_TENANT_MISMATCH, "SSO tenant mismatch.", 403)
        return await self._complete_provider_login(
            provider="ENTERPRISE_SSO",
            claims=claims,
            account_kind="ORGANIZATIONAL",
            org_id=org_id,
            method=AuthMethod.ENTERPRISE_SSO,
        )

    async def consume_saml_assertion(
        self,
        *,
        org_id: str,
        saml_response: str,
        request_id: str,
        session_secret: str,
    ) -> dict[str, Any]:
        async with self.engine.raw.connect() as conn:
            cfg = (
                await conn.execute(
                    select(organization_sso_configs).where(
                        organization_sso_configs.c.org_id == org_id
                    )
                )
            ).fetchone()
        if cfg is None or cfg.protocol != "SAML":
            raise forbidden(SSO_REQUIRED, "SAML is not configured.")
        config = SAMLConfig(
            idp_entity_id=cfg.idp_entity_id or cfg.issuer,
            idp_sso_url=cfg.idp_sso_url or cfg.issuer,
            idp_x509_cert=cfg.idp_x509_cert or "",
            sp_entity_id=cfg.client_id,
            acs_url=cfg.redirect_uri,
            session_secret=session_secret,
        )
        try:
            claims = parse_and_validate_response(saml_response, config, request_id)
        except Exception as exc:
            raise forbidden(PROVIDER_TOKEN_INVALID, "SAML assertion failed validation.") from exc
        replay_id = str(claims.raw.get("id") or claims.sub) + ":" + request_id
        await self.consume_replay("saml", hashlib.sha256(replay_id.encode()).hexdigest())
        token_claims = VerifiedIDToken(
            issuer=config.idp_entity_id,
            subject=claims.sub,
            audience=config.sp_entity_id,
            email=claims.email,
            hosted_domain=None,
            tenant_id=org_id,
            nonce=request_id,
            expires_at=int(time.time()) + 300,
            raw=claims.raw,
        )
        return await self._complete_provider_login(
            provider="ENTERPRISE_SSO",
            claims=token_claims,
            account_kind="ORGANIZATIONAL",
            org_id=org_id,
            method=AuthMethod.ENTERPRISE_SSO,
        )

    async def start_domain_challenge(
        self, *, org_id: str, domain: str, method: str, session: SessionAssurance, grant: str | None
    ) -> str:
        await self.require_step_up(
            session, SensitiveAction.CHANGE_COMPANY_DOMAIN, org_id=org_id, grant=grant
        )
        if method not in {"DNS_TXT", "HTTPS_WELL_KNOWN"}:
            raise forbidden(COMPANY_VERIFICATION_REQUIRED, "Unsupported domain challenge.")
        token = secrets.token_urlsafe(24)
        async with self.engine.raw.begin() as conn:
            await conn.execute(
                insert(company_domain_challenges).values(
                    id=str(uuid.uuid4()),
                    org_id=org_id,
                    domain=domain.lower(),
                    method=method,
                    token_hash=_hash(token),
                    status="PENDING",
                    created_at=_iso(),
                    expires_at=_iso(_now() + timedelta(hours=24)),
                )
            )
        return token

    async def complete_domain_challenge(
        self, *, org_id: str, domain: str, method: str, token: str
    ) -> None:
        async with self.engine.raw.begin() as conn:
            row = (
                await conn.execute(
                    select(company_domain_challenges).where(
                        company_domain_challenges.c.org_id == org_id,
                        company_domain_challenges.c.domain == domain.lower(),
                        company_domain_challenges.c.method == method,
                        company_domain_challenges.c.status == "PENDING",
                    )
                )
            ).fetchone()
            if row is None or _iso() >= row.expires_at or row.token_hash != _hash(token):
                raise forbidden(COMPANY_VERIFICATION_REQUIRED, "Domain challenge failed.")
            if method == "DNS_TXT":
                records = (self.txt_lookup or (lambda _d: []))(domain)
                if f"whitepact-verify={token}" not in records:
                    raise forbidden(COMPANY_VERIFICATION_REQUIRED, "DNS TXT challenge failed.")
            else:
                body = (self.well_known_lookup or (lambda _d: None))(domain)
                if body != token:
                    raise forbidden(
                        COMPANY_VERIFICATION_REQUIRED, "HTTPS well-known challenge failed."
                    )
            await conn.execute(
                update(company_domain_challenges)
                .where(company_domain_challenges.c.id == row.id)
                .values(status="VERIFIED", verified_at=_iso())
            )

    async def request_recovery(self, email: str) -> None:
        await self.limiter.check(f"recovery:{email.casefold()}", limit=5, window_seconds=300)
        from responsibleai.db.web_identity_repository import WebIdentityRepository

        _repo = WebIdentityRepository(self.engine)
        del _repo
        # Uniform work: always hash a token even if the account is unknown.
        token = secrets.token_urlsafe(32)
        _hash(token)
        async with self.engine.raw.connect() as conn:
            user = (
                await conn.execute(
                    select(web_users).where(
                        web_users.c.email == email.strip().casefold(), web_users.c.disabled == 0
                    )
                )
            ).fetchone()
        if user is None:
            return
        privileged = False
        async with self.engine.raw.connect() as conn:
            owner = (
                await conn.execute(
                    select(web_memberships).where(
                        web_memberships.c.user_id == user.id,
                        web_memberships.c.role.in_([Role.OWNER.value, "OWNER", "SECURITY_ADMIN"]),
                        web_memberships.c.status == "ACTIVE",
                    )
                )
            ).fetchone()
            privileged = owner is not None
        status = "RECOVERY_REVIEW" if privileged else "RECOVERY_CHALLENGED"
        async with self.engine.raw.begin() as conn:
            await conn.execute(
                insert(account_recovery_requests).values(
                    id=str(uuid.uuid4()),
                    user_id=user.id,
                    token_hash=_hash(token),
                    status=status,
                    privileged=1 if privileged else 0,
                    created_at=_iso(),
                    expires_at=_iso(_now() + timedelta(seconds=_RECOVERY_TTL)),
                    evidence_json=json.dumps({"delivery": "email"}),
                )
            )
        if privileged:
            await self._notify("suspicious_recovery", user_id=user.id)
        self.last_recovery_token_for_tests = token

    async def consume_recovery_token(
        self,
        token: str,
        *,
        user_id: str | None = None,
        recovery_code: str | None = None,
        passkey_ok: bool = False,
    ) -> str:
        await self.limiter.check("recovery-token", limit=20, window_seconds=60)
        if passkey_ok:
            raise EnterpriseError(
                RECOVERY_REVIEW_REQUIRED, "Passkey recovery must complete a WebAuthn ceremony.", 403
            )
        async with self.engine.raw.begin() as conn:
            row = (
                await conn.execute(
                    select(account_recovery_requests).where(
                        account_recovery_requests.c.token_hash == _hash(token)
                    )
                )
            ).fetchone()
            if row is None or row.consumed_at or _iso() >= row.expires_at:
                raise unauthenticated()
            if user_id and row.user_id != user_id:
                raise unauthenticated()
            recovered_user = row.user_id
            privileged = bool(row.privileged)
        if privileged:
            if not recovery_code:
                raise EnterpriseError(
                    RECOVERY_REVIEW_REQUIRED, "OWNER recovery cannot proceed from email alone.", 403
                )
            await self.consume_recovery_code(recovered_user, recovery_code)
        async with self.engine.raw.begin() as conn:
            row = (
                await conn.execute(
                    select(account_recovery_requests).where(
                        account_recovery_requests.c.token_hash == _hash(token)
                    )
                )
            ).fetchone()
            if row is None or row.consumed_at or _iso() >= row.expires_at:
                raise unauthenticated()
            result = await conn.execute(
                update(account_recovery_requests)
                .where(
                    account_recovery_requests.c.id == row.id,
                    account_recovery_requests.c.consumed_at.is_(None),
                )
                .values(consumed_at=_iso(), status="RECOVERY_CONSUMED")
            )
            if (result.rowcount or 0) != 1:
                raise EnterpriseError(CHALLENGE_REPLAY, "Recovery token already used.", 401)
            await conn.execute(
                update(web_sessions).where(web_sessions.c.user_id == row.user_id).values(revoked=1)
            )
            await conn.execute(
                update(step_up_grants)
                .where(
                    step_up_grants.c.user_id == row.user_id, step_up_grants.c.consumed_at.is_(None)
                )
                .values(consumed_at=_iso())
            )
            recovered_user = row.user_id
        await self._notify("password_reset", user_id=recovered_user)
        return recovered_user

    async def break_glass(
        self, *, org_id: str, user_id: str, session: SessionAssurance
    ) -> dict[str, str]:
        org = await self._org_policy(org_id)
        if not org.break_glass_user_id or org.break_glass_user_id != user_id:
            raise EnterpriseError(
                BREAK_GLASS_DENIED, "Break-glass is not configured for this identity.", 403
            )
        if not session.phishing_resistant:
            raise EnterpriseError(
                PASSKEY_REQUIRED, "Break-glass requires phishing-resistant authentication.", 403
            )
        async with self.engine.raw.connect() as conn:
            user = (
                await conn.execute(select(web_users).where(web_users.c.id == user_id))
            ).fetchone()
        if user is None or user.verification_status != "IDENTITY_VERIFIED":
            raise EnterpriseError(
                BREAK_GLASS_DENIED, "Break-glass identity must be IDENTITY_VERIFIED.", 403
            )
        if PRODUCTION_GATE_B_OPEN:
            raise RuntimeError("break-glass must not open Gate B")
        await self._notify(
            "break_glass", user_id=user_id, org_id=org_id, payload={"severity": "high"}
        )
        return {
            "status": "BREAK_GLASS_ACTIVE",
            "capabilities": "org_unlock_sso",
            "execution_authority": "denied",
        }

    async def evaluate_role_change(
        self, session: SessionAssurance, *, new_role: str, org_id: str
    ) -> None:
        org = await self._org_policy(org_id)
        if new_role in org.privileged_roles and not session.phishing_resistant:
            raise EnterpriseError(
                PASSKEY_REQUIRED, "Privilege elevation requires phishing-resistant step-up.", 403
            )


def parse_client_data_challenge(client_data_b64: str) -> str:
    from responsibleai.enterprise.security.webauthn import parse_client_data

    client = parse_client_data(client_data_b64)
    return b64url_encode(client.challenge)


def _unverified_iss(token: str) -> str:
    import base64
    import json as json_mod

    parts = token.split(".")
    if len(parts) != 3:
        raise forbidden(PROVIDER_TOKEN_INVALID, "Malformed token.")
    pad = "=" * ((4 - len(parts[1]) % 4) % 4)
    payload = json_mod.loads(base64.urlsafe_b64decode(parts[1] + pad))
    iss = str(payload.get("iss") or "")
    if "login.microsoftonline.com" not in iss:
        raise forbidden(PROVIDER_TOKEN_INVALID, "Unexpected Microsoft issuer.")
    return iss.rstrip("/")
