# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Identity verification provider abstraction and durable lifecycle.

Verification answers "who is this?". It is never execution authority.
Raw identity documents are not stored. Provider references are preferred.
"""

from __future__ import annotations

import hashlib
import hmac
import json
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
    CROSS_TENANT,
    FORBIDDEN,
    PROVIDER_REPLAY,
    PROVIDER_SIGNATURE_INVALID,
    forbidden,
)
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
        status = getattr(user, "verification_status", None) or "UNVERIFIED"
        if user.email_verified_at and status == "UNVERIFIED":
            status = "BASIC_VERIFIED"
        return {
            "user_id": user_id,
            "status": row.status if row else status,
            "email_verified": bool(user.email_verified_at),
            "provider": row.provider if row else None,
            "assurance_level": row.assurance_level if row else None,
            "verified_at": row.verified_at if row else None,
            "expires_at": row.expires_at if row else None,
            "review_status": row.review_status if row else None,
        }

    async def start_human_verification(
        self, user_id: str, *, request_id: str | None = None
    ) -> dict[str, Any]:
        session = self._provider.start_session(subject_id=user_id, return_url=None)
        now = _iso()
        rec_id = str(uuid.uuid4())
        async with self._engine.raw.begin() as conn:
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
            outcome = str(event.get("outcome") or "").upper()
            if org_id and event.get("kind") == "organization":
                return await self._apply_org_outcome(
                    conn, org_id=org_id, outcome=outcome, event=event, request_id=request_id
                )
            if not subject:
                raise forbidden(FORBIDDEN, "Human verification event missing subject.")
            return await self._apply_human_outcome(
                conn, user_id=subject, outcome=outcome, event=event, request_id=request_id
            )

    async def _apply_human_outcome(
        self,
        conn: Any,
        *,
        user_id: str,
        outcome: str,
        event: dict[str, Any],
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
        now = _iso()
        expires = None
        if status == "IDENTITY_VERIFIED":
            expires = _iso(_now() + timedelta(days=365))
        row = (
            await conn.execute(
                select(identity_verifications)
                .where(identity_verifications.c.user_id == user_id)
                .order_by(identity_verifications.c.updated_at.desc())
            )
        ).fetchone()
        if row is None:
            await conn.execute(
                insert(identity_verifications).values(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    status=status,
                    provider=self._provider.name,
                    provider_reference_id=str(event.get("reference_id") or event.get("event_id")),
                    country=event.get("country"),
                    assurance_level=event.get("assurance_level"),
                    review_status=event.get("review_status"),
                    verified_at=now if status == "IDENTITY_VERIFIED" else None,
                    expires_at=expires,
                    created_at=now,
                    updated_at=now,
                )
            )
        else:
            await conn.execute(
                update(identity_verifications)
                .where(identity_verifications.c.id == row.id)
                .values(
                    status=status,
                    provider_reference_id=str(event.get("reference_id") or event.get("event_id")),
                    country=event.get("country"),
                    assurance_level=event.get("assurance_level"),
                    review_status=event.get("review_status"),
                    verified_at=now if status == "IDENTITY_VERIFIED" else row.verified_at,
                    expires_at=expires,
                    updated_at=now,
                )
            )
        await conn.execute(
            update(web_users)
            .where(web_users.c.id == user_id)
            .values(verification_status=status, updated_at=now)
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
        self, conn: Any, *, org_id: str, outcome: str, event: dict[str, Any], request_id: str | None
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
            if owner is None or owner.verification_status != "IDENTITY_VERIFIED":
                raise forbidden(
                    FORBIDDEN,
                    "Organization verification requires an individually verified accountable owner.",
                )
        now = _iso()
        existing = (
            await conn.execute(
                select(organization_verifications).where(
                    organization_verifications.c.org_id == org_id
                )
            )
        ).fetchone()
        values = {
            "status": status,
            "legal_name": event.get("legal_name"),
            "domain": event.get("domain"),
            "registration_reference": event.get("registration_reference"),
            "accountable_owner_user_id": event.get("accountable_owner_user_id"),
            "provider": self._provider.name,
            "provider_reference_id": str(event.get("reference_id") or event.get("event_id")),
            "verified_at": now if status == "ORGANIZATION_VERIFIED" else None,
            "updated_at": now,
        }
        if existing is None:
            await conn.execute(
                insert(organization_verifications).values(
                    id=str(uuid.uuid4()),
                    org_id=org_id,
                    created_at=now,
                    **values,
                )
            )
        else:
            await conn.execute(
                update(organization_verifications)
                .where(organization_verifications.c.org_id == org_id)
                .values(**values)
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
            mapped = {
                "IDENTITY_VERIFIED": "ORGANIZATION_VERIFIED",
                "BASIC_VERIFIED": "UNVERIFIED",
            }.get(human.get("status", "UNVERIFIED"), "UNVERIFIED")
            return {
                "org_id": org_id,
                "workspace_kind": kind,
                "status": mapped
                if mapped != "UNVERIFIED"
                else (row.status if row else "UNVERIFIED"),
                "individual_status": human.get("status"),
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
        session = self._provider.start_session(subject_id=org_id, return_url=None)
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
