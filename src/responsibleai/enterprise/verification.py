# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Identity verification provider abstraction and durable lifecycle.

Verification answers "who is this?". It is never execution authority.
Raw identity documents are not stored. Provider references are preferred.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError

from responsibleai.db.engine import (
    DatabaseEngine,
    identity_provider_events,
    identity_verifications,
    organization_verifications,
    organizations,
    web_memberships,
    web_users,
)
from responsibleai.enterprise.audit import EnterpriseAuditLog
from responsibleai.enterprise.errors import (
    ASSURANCE_NOT_APPROVED,
    CROSS_TENANT,
    FORBIDDEN,
    PROVIDER_REPLAY,
    PROVIDER_SIGNATURE_INVALID,
    VERIFICATION_CONFLICT,
    VERIFICATION_SESSION_REQUIRED,
    VERIFICATION_SESSION_UNKNOWN,
    VERIFICATION_SUSPENDED,
    VERIFICATION_TRANSITION_DENIED,
    EnterpriseError,
    forbidden,
)
from responsibleai.environment import is_production
from responsibleai.rbac.models import Role

HUMAN_STATES = (
    "UNVERIFIED",
    "BASIC_VERIFIED",
    "IDENTITY_VERIFIED",
    "REVIEW_REQUIRED",
    "REJECTED",
    "SUSPENDED",
)
ORG_STATES = (
    "UNVERIFIED",
    "DOMAIN_VERIFIED",
    "ORGANIZATION_VERIFIED",
    "REVIEW_REQUIRED",
    "REJECTED",
    "SUSPENDED",
)

# The reference adapter is a development contract. A signature from it is not
# independent proof that a human completed identity verification.
REFERENCE_PROVIDER = "hmac-reference"
DEVELOPMENT_ONLY_PROVIDERS = frozenset({REFERENCE_PROVIDER})
ACCEPTED_EVENT_TYPES = frozenset({"identity.verification", "identity.revocation"})
# These names describe login or sandbox signals. They are never identity proofing,
# even if a deployment lists them in configuration.
REJECTED_ASSURANCE_LEVELS = frozenset(
    {
        "email",
        "basic",
        "basic_verified",
        "sso",
        "passkey",
        "webauthn",
        "sandbox",
        "synthetic",
        "persona_sandbox",
        "hmac",
        "hmac-reference",
        "reference",
    }
)
HUMAN_TRANSITIONS = {
    "UNVERIFIED": frozenset(
        {"BASIC_VERIFIED", "REVIEW_REQUIRED", "REJECTED", "SUSPENDED", "IDENTITY_VERIFIED"}
    ),
    "REVIEW_REQUIRED": frozenset(
        {"BASIC_VERIFIED", "REVIEW_REQUIRED", "REJECTED", "SUSPENDED", "IDENTITY_VERIFIED"}
    ),
    "BASIC_VERIFIED": frozenset(
        {"BASIC_VERIFIED", "REVIEW_REQUIRED", "REJECTED", "SUSPENDED", "IDENTITY_VERIFIED"}
    ),
    "IDENTITY_VERIFIED": frozenset({"IDENTITY_VERIFIED", "SUSPENDED", "REJECTED"}),
    "REJECTED": frozenset({"REJECTED", "REVIEW_REQUIRED", "SUSPENDED"}),
    "SUSPENDED": frozenset({"SUSPENDED"}),
}
ORG_TRANSITIONS = {
    "UNVERIFIED": frozenset(
        {"DOMAIN_VERIFIED", "ORGANIZATION_VERIFIED", "REVIEW_REQUIRED", "REJECTED", "SUSPENDED"}
    ),
    "REVIEW_REQUIRED": frozenset(
        {"DOMAIN_VERIFIED", "ORGANIZATION_VERIFIED", "REVIEW_REQUIRED", "REJECTED", "SUSPENDED"}
    ),
    "DOMAIN_VERIFIED": frozenset(
        {"DOMAIN_VERIFIED", "ORGANIZATION_VERIFIED", "REVIEW_REQUIRED", "REJECTED", "SUSPENDED"}
    ),
    "ORGANIZATION_VERIFIED": frozenset({"ORGANIZATION_VERIFIED", "SUSPENDED", "REJECTED"}),
    "REJECTED": frozenset({"REJECTED", "REVIEW_REQUIRED", "SUSPENDED"}),
    "SUSPENDED": frozenset({"SUSPENDED"}),
}


def _split_csv(value: str) -> frozenset[str]:
    return frozenset(item.strip() for item in value.split(",") if item.strip())


def approved_identity_policy() -> tuple[frozenset[str], frozenset[str], bool]:
    """Return (providers, assurance levels, reference contract enabled).

    Missing configuration is fail-closed. Nothing is approved by default.
    ``hmac-reference`` is ignored unless the explicit reference-contract switch
    is on, and it is never approved when the process is production.
    """
    providers = _split_csv(os.environ.get("WHITEPACT_IDENTITY_APPROVED_PROVIDERS", ""))
    levels = _split_csv(os.environ.get("WHITEPACT_IDENTITY_APPROVED_ASSURANCE_LEVELS", ""))
    reference = os.environ.get("WHITEPACT_IDENTITY_REFERENCE_CONTRACT") == "1"
    return providers, levels, reference


def identity_assurance_accepted(provider: str | None, assurance_level: str | None) -> bool:
    """True only for an explicitly approved provider and assurance standard."""
    if not provider or not assurance_level:
        return False
    normalized = assurance_level.strip()
    if normalized.lower() in REJECTED_ASSURANCE_LEVELS:
        return False
    if provider == "didit-sandbox" and (
        is_production() or os.environ.get("WHITEPACT_DIDIT_SANDBOX_ASSURANCE_ENABLED") != "1"
    ):
        return False
    if is_production() and provider in DEVELOPMENT_ONLY_PROVIDERS:
        return False
    providers, levels, reference = approved_identity_policy()
    if provider in DEVELOPMENT_ONLY_PROVIDERS and not reference:
        return False
    if provider not in providers or normalized not in levels:
        return False
    return True


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _expired(expires_at: str | None) -> bool:
    parsed = _parse_time(expires_at)
    if parsed is None:
        return True
    return parsed <= _now()


def effective_human_status(user: Any, row: Any) -> str:
    """Project the status credential issuance is allowed to trust."""
    if user is not None and getattr(user, "verification_status", None) == "SUSPENDED":
        return "SUSPENDED"
    if row is None:
        status = getattr(user, "verification_status", None) or "UNVERIFIED"
        if status == "IDENTITY_VERIFIED":
            return "UNVERIFIED"
        if user is not None and user.email_verified_at and status == "UNVERIFIED":
            return "BASIC_VERIFIED"
        return status
    status = row.status
    if status == "IDENTITY_VERIFIED":
        if _expired(row.expires_at):
            return "EXPIRED"
        if not identity_assurance_accepted(row.provider, row.assurance_level):
            return "UNVERIFIED"
    return status


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).isoformat()


class IdentityVerificationProvider(Protocol):
    name: str

    def start_session(self, *, subject_id: str, return_url: str | None) -> dict[str, str]:
        """Return provider-hosted session metadata. Never returns verified=true from the client."""

    def verify_webhook(self, *, payload: bytes, signature: str, timestamp: str) -> dict[str, Any]:
        """Validate signature and return canonical event dict."""


class HmacVerificationProvider:
    """Default provider adapter. Real vendors plug in with the same contract.

    WhitePact core never hardcodes a commercial KYC vendor as authority.
    """

    name = "hmac-reference"

    def __init__(self, webhook_secret: str) -> None:
        self._secret = webhook_secret.encode("utf-8")

    def start_session(self, *, subject_id: str, return_url: str | None) -> dict[str, str]:
        return {
            "provider": self.name,
            "session_id": "sess_" + secrets.token_urlsafe(16),
            "subject_id": subject_id,
            "hosted_url": return_url or "",
        }

    def verify_webhook(self, *, payload: bytes, signature: str, timestamp: str) -> dict[str, Any]:
        expected = hmac.new(self._secret, payload + timestamp.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise forbidden(PROVIDER_SIGNATURE_INVALID, "Provider webhook signature is invalid.")
        try:
            ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise forbidden(PROVIDER_SIGNATURE_INVALID, "Provider timestamp is invalid.") from exc
        if abs((_now() - ts.astimezone(UTC)).total_seconds()) > 300:
            raise forbidden(PROVIDER_SIGNATURE_INVALID, "Provider webhook timestamp is stale.")
        body = json.loads(payload.decode("utf-8"))
        if not isinstance(body, dict) or "event_id" not in body:
            raise forbidden(PROVIDER_SIGNATURE_INVALID, "Provider event is malformed.")
        if body.get("verified") is True and "subject_id" not in body:
            raise forbidden(PROVIDER_SIGNATURE_INVALID, "Provider event missing subject binding.")
        return body


class VerificationService:
    def __init__(self, engine: DatabaseEngine, provider: IdentityVerificationProvider) -> None:
        self._engine = engine
        self._provider = provider
        self.audit = EnterpriseAuditLog(engine)

    async def get_human_status(self, user_id: str) -> dict[str, Any]:
        async with self._engine.raw.connect() as conn:
            user = (
                await conn.execute(select(web_users).where(web_users.c.id == user_id))
            ).fetchone()
            row = (
                await conn.execute(
                    select(identity_verifications)
                    .where(identity_verifications.c.user_id == user_id)
                    .order_by(identity_verifications.c.updated_at.desc())
                )
            ).fetchone()
        if user is None:
            raise forbidden(FORBIDDEN, "User not found.")
        status = effective_human_status(user, row)
        accepted = status == "IDENTITY_VERIFIED"
        return {
            "user_id": user_id,
            "status": status,
            "email_verified": bool(user.email_verified_at),
            "provider": row.provider if row else None,
            "assurance_level": row.assurance_level if row and accepted else None,
            "assurance_accepted": accepted,
            "verified_at": row.verified_at if row and accepted else None,
            "expires_at": row.expires_at if row else None,
            "review_status": row.review_status if row else None,
            "stored_status": row.status if row else getattr(user, "verification_status", None),
        }

    async def start_human_verification(
        self, user_id: str, *, request_id: str | None = None
    ) -> dict[str, Any]:
        async with self._engine.raw.connect() as conn:
            user = (
                await conn.execute(select(web_users).where(web_users.c.id == user_id))
            ).fetchone()
        if user is None:
            raise forbidden(FORBIDDEN, "User not found.")
        if user.verification_status == "SUSPENDED":
            raise forbidden(
                VERIFICATION_SUSPENDED,
                "A suspended identity cannot open a new verification session.",
            )
        session = await asyncio.to_thread(
            self._provider.start_session, subject_id=user_id, return_url=None
        )
        now = _iso()
        rec_id = str(uuid.uuid4())
        async with self._engine.raw.begin() as conn:
            duplicate = (
                await conn.execute(
                    select(identity_verifications.c.id).where(
                        identity_verifications.c.provider == self._provider.name,
                        identity_verifications.c.provider_reference_id == session["session_id"],
                    )
                )
            ).fetchone()
            if duplicate is not None:
                raise forbidden(
                    VERIFICATION_CONFLICT,
                    "Provider session reference is already in use.",
                )
            await conn.execute(
                insert(identity_verifications).values(
                    id=rec_id,
                    user_id=user_id,
                    status="REVIEW_REQUIRED",
                    provider=self._provider.name,
                    provider_reference_id=session["session_id"],
                    created_at=now,
                    updated_at=now,
                )
            )
        await self.audit.record(
            actor_type="human",
            actor_id=user_id,
            action="verification.initiated",
            target_type="user",
            target_id=user_id,
            result="ALLOWED",
            request_id=request_id,
            metadata={"provider": self._provider.name},
        )
        return {"verification_id": rec_id, **session, "status": "REVIEW_REQUIRED"}

    async def apply_provider_event(
        self,
        *,
        payload: bytes,
        signature: str,
        timestamp: str,
        expected_user_id: str | None = None,
        expected_org_id: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        event = self._provider.verify_webhook(
            payload=payload, signature=signature, timestamp=timestamp
        )
        # Client-supplied verified=true is ignored unless the provider adapter accepted the signature.
        event_id = str(event["event_id"])
        payload_hash = hashlib.sha256(payload).hexdigest()
        try:
            return await self._apply_verified_event(
                event,
                event_id=event_id,
                payload_hash=payload_hash,
                expected_user_id=expected_user_id,
                expected_org_id=expected_org_id,
                request_id=request_id,
            )
        except EnterpriseError as exc:
            await self.audit.record(
                actor_type="provider",
                actor_id=self._provider.name,
                action="verification.denied",
                target_type="user" if event.get("subject_id") else "organization",
                target_id=str(event.get("subject_id") or event.get("org_id") or ""),
                result="DENIED",
                request_id=request_id,
                metadata={
                    "reason": exc.code,
                    "event_id": event_id,
                    "provider": self._provider.name,
                },
            )
            raise

    async def _apply_verified_event(
        self,
        event: dict[str, Any],
        *,
        event_id: str,
        payload_hash: str,
        expected_user_id: str | None,
        expected_org_id: str | None,
        request_id: str | None,
    ) -> dict[str, Any]:
        async with self._engine.raw.begin() as conn:
            try:
                await conn.execute(
                    insert(identity_provider_events).values(
                        id=str(uuid.uuid4()),
                        provider=self._provider.name,
                        event_id=event_id,
                        user_id=event.get("subject_id"),
                        org_id=event.get("org_id"),
                        payload_hash=payload_hash,
                        received_at=_iso(),
                    )
                )
            except IntegrityError as exc:
                raise forbidden(
                    PROVIDER_REPLAY, "Provider event has already been processed."
                ) from exc
            subject = event.get("subject_id")
            org_id = event.get("org_id")
            if expected_user_id and subject != expected_user_id:
                raise forbidden(CROSS_TENANT, "Verification event is not bound to this account.")
            if expected_org_id and org_id and org_id != expected_org_id:
                raise forbidden(
                    CROSS_TENANT, "Verification event is not bound to this organization."
                )
            event_type = str(event.get("event_type") or "")
            if event_type not in ACCEPTED_EVENT_TYPES:
                raise forbidden(PROVIDER_SIGNATURE_INVALID, "Provider event type is not accepted.")
            reference_id = str(event.get("reference_id") or "")
            if not reference_id:
                raise forbidden(
                    VERIFICATION_SESSION_REQUIRED,
                    "Provider event is missing the verification session reference.",
                )
            outcome = str(event.get("outcome") or "").upper()
            if event_type == "identity.revocation" and outcome not in {"SUSPENDED", "REJECTED"}:
                raise forbidden(
                    VERIFICATION_TRANSITION_DENIED,
                    "A revocation event cannot elevate identity.",
                )
            if org_id and event.get("kind") == "organization":
                return await self._apply_org_outcome(
                    conn,
                    org_id=str(org_id),
                    outcome=outcome,
                    event=event,
                    reference_id=reference_id,
                    request_id=request_id,
                )
            if not subject:
                raise forbidden(FORBIDDEN, "Human verification event missing subject.")
            return await self._apply_human_outcome(
                conn,
                claimed_user_id=str(subject),
                outcome=outcome,
                event=event,
                reference_id=reference_id,
                request_id=request_id,
            )

    async def _apply_human_outcome(
        self,
        conn: Any,
        *,
        claimed_user_id: str,
        outcome: str,
        event: dict[str, Any],
        reference_id: str,
        request_id: str | None,
    ) -> dict[str, Any]:
        mapping = {
            "VERIFIED": "IDENTITY_VERIFIED",
            "BASIC": "BASIC_VERIFIED",
            "REVIEW": "REVIEW_REQUIRED",
            "REJECTED": "REJECTED",
            "SUSPENDED": "SUSPENDED",
            "FAILED": "REJECTED",
        }
        status = mapping.get(outcome)
        if status is None:
            raise forbidden(FORBIDDEN, "Unrecognized verification outcome.")
        row = (
            await conn.execute(
                select(identity_verifications).where(
                    identity_verifications.c.provider == self._provider.name,
                    identity_verifications.c.provider_reference_id == reference_id,
                )
            )
        ).fetchone()
        if row is None:
            raise forbidden(
                VERIFICATION_SESSION_UNKNOWN,
                "Provider event does not match an initiated verification session.",
            )
        user_id = row.user_id
        if claimed_user_id != user_id:
            raise forbidden(
                CROSS_TENANT,
                "Provider subject does not match the verification session.",
            )
        account = (
            await conn.execute(select(web_users).where(web_users.c.id == user_id))
        ).fetchone()
        if (
            account is not None
            and account.verification_status == "SUSPENDED"
            and status == "IDENTITY_VERIFIED"
        ):
            raise forbidden(
                VERIFICATION_TRANSITION_DENIED,
                "Suspended identity cannot be restored by a provider callback.",
            )
        if event.get("org_id"):
            member = (
                await conn.execute(
                    select(web_memberships.c.id).where(
                        web_memberships.c.user_id == user_id,
                        web_memberships.c.org_id == str(event.get("org_id")),
                        web_memberships.c.status == "ACTIVE",
                    )
                )
            ).fetchone()
            if member is None:
                raise forbidden(
                    CROSS_TENANT, "Verification event is not bound to this organization."
                )
        allowed = HUMAN_TRANSITIONS.get(row.status, frozenset())
        if status not in allowed:
            raise forbidden(
                VERIFICATION_TRANSITION_DENIED,
                "Verification state transition is not allowed.",
            )
        assurance = event.get("assurance_level")
        if isinstance(assurance, str):
            assurance = assurance.strip() or None
        else:
            assurance = None
        if status == "IDENTITY_VERIFIED" and not identity_assurance_accepted(
            self._provider.name, assurance if isinstance(assurance, str) else None
        ):
            raise forbidden(
                ASSURANCE_NOT_APPROVED,
                "IDENTITY_VERIFIED requires an approved provider and assurance standard.",
            )
        if (
            row.status == "IDENTITY_VERIFIED"
            and status == "IDENTITY_VERIFIED"
            and row.assurance_level
            and assurance
            and assurance != row.assurance_level
            and not identity_assurance_accepted(self._provider.name, assurance)
        ):
            raise forbidden(
                ASSURANCE_NOT_APPROVED,
                "A later assurance value is not an approved standard.",
            )
        now = _iso()
        expires = None
        if status == "IDENTITY_VERIFIED":
            expires = _iso(_now() + timedelta(days=365))
        changed = await conn.execute(
            update(identity_verifications)
            .where(
                identity_verifications.c.id == row.id,
                identity_verifications.c.status == row.status,
            )
            .values(
                status=status,
                country=event.get("country"),
                assurance_level=assurance if status == "IDENTITY_VERIFIED" else row.assurance_level,
                review_status=event.get("review_status"),
                verified_at=now if status == "IDENTITY_VERIFIED" else row.verified_at,
                expires_at=expires if status == "IDENTITY_VERIFIED" else row.expires_at,
                updated_at=now,
            )
        )
        if changed.rowcount != 1:
            raise forbidden(VERIFICATION_CONFLICT, "Verification session changed concurrently.")
        user_status = status if status != "BASIC_VERIFIED" else "BASIC_VERIFIED"
        if status == "IDENTITY_VERIFIED":
            user_status = "IDENTITY_VERIFIED"
        elif status in {"SUSPENDED", "REJECTED"}:
            user_status = status
        elif row.status == "IDENTITY_VERIFIED":
            user_status = "IDENTITY_VERIFIED"
        else:
            user_status = status
        await conn.execute(
            update(web_users)
            .where(web_users.c.id == user_id)
            .values(verification_status=user_status, updated_at=now)
        )
        action = {
            "IDENTITY_VERIFIED": "verification.completed",
            "BASIC_VERIFIED": "verification.completed",
            "REVIEW_REQUIRED": "verification.review_requested",
            "REJECTED": "verification.failed",
            "SUSPENDED": "verification.suspended",
        }[status]
        await self.audit.record(
            actor_type="provider",
            actor_id=self._provider.name,
            action=action,
            target_type="user",
            target_id=user_id,
            result="ALLOWED",
            request_id=request_id,
            metadata={"status": status, "assurance_level": event.get("assurance_level")},
            conn=conn,
        )
        if status in {"SUSPENDED", "REJECTED"}:
            from responsibleai.db.engine import org_api_keys

            await conn.execute(
                update(org_api_keys)
                .where(
                    org_api_keys.c.accountable_human_user_id == user_id, org_api_keys.c.revoked == 0
                )
                .values(revoked=1, revoked_at=now)
            )
        return {"user_id": user_id, "status": status}

    async def _apply_org_outcome(
        self,
        conn: Any,
        *,
        org_id: str,
        outcome: str,
        event: dict[str, Any],
        reference_id: str,
        request_id: str | None,
    ) -> dict[str, Any]:
        mapping = {
            "DOMAIN": "DOMAIN_VERIFIED",
            "VERIFIED": "ORGANIZATION_VERIFIED",
            "REVIEW": "REVIEW_REQUIRED",
            "REJECTED": "REJECTED",
            "SUSPENDED": "SUSPENDED",
        }
        status = mapping.get(outcome)
        if status is None:
            raise forbidden(FORBIDDEN, "Unrecognized organization verification outcome.")
        existing = (
            await conn.execute(
                select(organization_verifications).where(
                    organization_verifications.c.provider == self._provider.name,
                    organization_verifications.c.provider_reference_id == reference_id,
                )
            )
        ).fetchone()
        if existing is None or existing.org_id != org_id:
            raise forbidden(
                VERIFICATION_SESSION_UNKNOWN,
                "Provider event does not match an initiated organization verification.",
            )
        if status == "ORGANIZATION_VERIFIED":
            owner = (
                await conn.execute(
                    select(web_memberships.c.user_id, web_users.c.verification_status)
                    .join(web_users, web_users.c.id == web_memberships.c.user_id)
                    .where(
                        web_memberships.c.org_id == org_id,
                        web_memberships.c.role == Role.OWNER.value,
                        web_memberships.c.status == "ACTIVE",
                    )
                )
            ).fetchone()
            owner_row = None
            owner_user = None
            if owner is not None:
                owner_user = (
                    await conn.execute(select(web_users).where(web_users.c.id == owner.user_id))
                ).fetchone()
                owner_row = (
                    await conn.execute(
                        select(identity_verifications)
                        .where(identity_verifications.c.user_id == owner.user_id)
                        .order_by(identity_verifications.c.updated_at.desc())
                    )
                ).fetchone()
            if (
                owner is None
                or effective_human_status(owner_user, owner_row) != "IDENTITY_VERIFIED"
            ):
                raise forbidden(
                    FORBIDDEN,
                    "Organization verification requires an individually verified accountable owner.",
                )
        allowed = ORG_TRANSITIONS.get(existing.status, frozenset())
        if status not in allowed:
            raise forbidden(
                VERIFICATION_TRANSITION_DENIED,
                "Organization verification state transition is not allowed.",
            )
        now = _iso()
        values = {
            "status": status,
            "legal_name": event.get("legal_name"),
            "domain": event.get("domain"),
            "registration_reference": event.get("registration_reference"),
            "accountable_owner_user_id": event.get("accountable_owner_user_id"),
            "provider": self._provider.name,
            "verified_at": now if status == "ORGANIZATION_VERIFIED" else existing.verified_at,
            "updated_at": now,
        }
        changed = await conn.execute(
            update(organization_verifications)
            .where(
                organization_verifications.c.org_id == org_id,
                organization_verifications.c.status == existing.status,
            )
            .values(**values)
        )
        if changed.rowcount != 1:
            raise forbidden(
                VERIFICATION_CONFLICT, "Organization verification changed concurrently."
            )
        await self.audit.record(
            org_id=org_id,
            actor_type="provider",
            actor_id=self._provider.name,
            action="organization.verification_changed",
            target_type="organization",
            target_id=org_id,
            result="ALLOWED",
            request_id=request_id,
            metadata={"status": status},
            conn=conn,
        )
        if status in {"SUSPENDED", "REJECTED"}:
            from responsibleai.db.engine import org_api_keys, web_sessions

            await conn.execute(
                update(org_api_keys)
                .where(org_api_keys.c.org_id == org_id, org_api_keys.c.revoked == 0)
                .values(revoked=1, revoked_at=now)
            )
            await conn.execute(
                update(web_sessions).where(web_sessions.c.org_id == org_id).values(revoked=1)
            )
        return {"org_id": org_id, "status": status}

    async def get_org_status(self, org_id: str) -> dict[str, Any]:
        async with self._engine.raw.connect() as conn:
            org = (
                await conn.execute(select(organizations).where(organizations.c.id == org_id))
            ).fetchone()
            row = (
                await conn.execute(
                    select(organization_verifications).where(
                        organization_verifications.c.org_id == org_id
                    )
                )
            ).fetchone()
        if org is None:
            raise forbidden(FORBIDDEN, "Organization not found.")
        kind = getattr(org, "workspace_kind", None) or "ORGANIZATION"
        if kind == "INDIVIDUAL":
            human = (
                await self.get_human_status(org.owner_user_id)
                if org.owner_user_id
                else {"status": "UNVERIFIED"}
            )
            human_status = human.get("status", "UNVERIFIED")
            if human_status == "IDENTITY_VERIFIED":
                effective = "ORGANIZATION_VERIFIED"
            elif human_status == "SUSPENDED":
                effective = "SUSPENDED"
            else:
                effective = "UNVERIFIED"
            return {
                "org_id": org_id,
                "workspace_kind": kind,
                "status": effective,
                "stored_status": row.status if row else None,
                "individual_status": human_status,
            }
        return {
            "org_id": org_id,
            "workspace_kind": kind,
            "status": row.status if row else "UNVERIFIED",
            "legal_name": row.legal_name if row else None,
            "domain": row.domain if row else None,
            "accountable_owner_user_id": row.accountable_owner_user_id
            if row
            else org.owner_user_id,
        }

    async def start_org_verification(
        self, org_id: str, *, actor_user_id: str, request_id: str | None = None
    ) -> dict[str, Any]:
        session = await asyncio.to_thread(
            self._provider.start_session, subject_id=org_id, return_url=None
        )
        now = _iso()
        rec_id = str(uuid.uuid4())
        async with self._engine.raw.begin() as conn:
            existing = (
                await conn.execute(
                    select(organization_verifications.c.id).where(
                        organization_verifications.c.org_id == org_id
                    )
                )
            ).fetchone()
            if existing is None:
                await conn.execute(
                    insert(organization_verifications).values(
                        id=rec_id,
                        org_id=org_id,
                        status="REVIEW_REQUIRED",
                        provider=self._provider.name,
                        provider_reference_id=session["session_id"],
                        accountable_owner_user_id=actor_user_id,
                        created_at=now,
                        updated_at=now,
                    )
                )
            else:
                rec_id = existing.id
                await conn.execute(
                    update(organization_verifications)
                    .where(organization_verifications.c.org_id == org_id)
                    .values(status="REVIEW_REQUIRED", updated_at=now)
                )
        await self.audit.record(
            org_id=org_id,
            actor_type="human",
            actor_id=actor_user_id,
            action="verification.initiated",
            target_type="organization",
            target_id=org_id,
            result="ALLOWED",
            request_id=request_id,
        )
        return {"verification_id": rec_id, **session, "status": "REVIEW_REQUIRED"}

    async def suspend_human(self, user_id: str, *, request_id: str | None = None) -> None:
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                update(web_users)
                .where(web_users.c.id == user_id)
                .values(verification_status="SUSPENDED")
            )
            await conn.execute(
                update(identity_verifications)
                .where(identity_verifications.c.user_id == user_id)
                .values(status="SUSPENDED", updated_at=_iso())
            )
            from responsibleai.db.engine import org_api_keys, web_sessions

            await conn.execute(
                update(org_api_keys)
                .where(
                    org_api_keys.c.accountable_human_user_id == user_id, org_api_keys.c.revoked == 0
                )
                .values(revoked=1, revoked_at=_iso())
            )
            await conn.execute(
                update(web_sessions).where(web_sessions.c.user_id == user_id).values(revoked=1)
            )
        await self.audit.record(
            actor_type="system",
            actor_id="security",
            action="verification.suspended",
            target_type="user",
            target_id=user_id,
            result="ALLOWED",
            request_id=request_id,
        )

    async def restore_human_to_unverified(self, user_id: str) -> None:
        """Restoring verification never resurrects revoked credentials."""
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                update(web_users)
                .where(web_users.c.id == user_id)
                .values(verification_status="UNVERIFIED")
            )
        await self.audit.record(
            actor_type="system",
            actor_id="security",
            action="verification.restored",
            target_type="user",
            target_id=user_id,
            result="ALLOWED",
            metadata={"note": "revoked_credentials_remain_revoked"},
        )
