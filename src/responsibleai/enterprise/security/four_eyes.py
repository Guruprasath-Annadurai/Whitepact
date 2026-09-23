# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Layer 2 four-eyes (maker-checker) for privileged identity-security mutations.

Identity four-eyes is administrative dual control. It never mints execution
authority. Break-glass, mailbox recovery, and service accounts cannot be the
second eye.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.exc import SQLAlchemyError

from responsibleai.db.engine import (
    DatabaseEngine,
    enterprise_service_accounts,
    identity_four_eyes_requests,
    web_memberships,
    web_users,
)
from responsibleai.enterprise.errors import EnterpriseError, forbidden
from responsibleai.enterprise.security.policy import (
    ASSURANCE_RANK,
    SensitiveAction,
    SessionAssurance,
)
from responsibleai.rbac.models import Role

DEFAULT_DUAL_CONTROL_ACTIONS = frozenset(
    {
        SensitiveAction.DISABLE_REQUIRED_SSO.value,
        SensitiveAction.TRANSFER_OWNERSHIP.value,
        SensitiveAction.PROMOTE_OWNER.value,
        SensitiveAction.PROMOTE_SECURITY_ADMIN.value,
        SensitiveAction.CHANGE_COMPANY_DOMAIN.value,
        SensitiveAction.CHANGE_ENTRA_BINDING.value,
        SensitiveAction.CHANGE_GOOGLE_WORKSPACE_BINDING.value,
        SensitiveAction.EMERGENCY_SECURITY_SETTINGS.value,
        SensitiveAction.HIGH_RISK_RECOVERY.value,
    }
)

PRIVILEGED_APPROVER_ROLES = frozenset({Role.OWNER.value, "OWNER", "SECURITY_ADMIN"})


class FourEyesState(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    EXPIRED = "EXPIRED"
    CONSUMED = "CONSUMED"
    REVOKED = "REVOKED"


def canonical_action_digest(action: str, parameters: dict[str, Any]) -> str:
    payload = {"action": action, "parameters": parameters}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class IdentityFourEyesRequest:
    id: str
    org_id: str
    requester_user_id: str
    action: str
    digest: str
    status: str
    created_at: str
    expires_at: str
    approver_user_id: str | None = None
    parameters: dict[str, Any] | None = None


class IdentityFourEyesService:
    def __init__(self, engine: DatabaseEngine) -> None:
        self.engine = engine

    async def request(
        self,
        *,
        org_id: str,
        requester: SessionAssurance,
        action: str,
        parameters: dict[str, Any],
        ttl_minutes: int = 120,
        security_version: str | None = None,
    ) -> IdentityFourEyesRequest:
        if not org_id or requester.org_id != org_id:
            raise forbidden("CROSS_TENANT", "Four-eyes requests are bound to one organization.")
        await self._assert_human_privileged(org_id, requester.user_id)
        params = dict(parameters)
        if security_version:
            params["security_version"] = security_version
        digest = canonical_action_digest(action, params)
        now = datetime.now(UTC)
        req_id = str(uuid.uuid4())
        created = now.isoformat()
        expires = (now + timedelta(minutes=ttl_minutes)).isoformat()
        try:
            async with self.engine.raw.begin() as conn:
                await conn.execute(
                    insert(identity_four_eyes_requests).values(
                        id=req_id,
                        org_id=org_id,
                        requester_user_id=requester.user_id,
                        action=action,
                        parameters_json=json.dumps(params, sort_keys=True),
                        action_digest=digest,
                        security_version=security_version,
                        status=FourEyesState.PENDING.value,
                        created_at=created,
                        expires_at=expires,
                    )
                )
        except SQLAlchemyError as exc:
            raise EnterpriseError(
                "IDENTITY_PROTECTION_UNAVAILABLE",
                "Four-eyes storage is unavailable.",
                503,
            ) from exc
        return IdentityFourEyesRequest(
            id=req_id,
            org_id=org_id,
            requester_user_id=requester.user_id,
            action=action,
            digest=digest,
            status=FourEyesState.PENDING.value,
            created_at=created,
            expires_at=expires,
            parameters=params,
        )

    async def approve(
        self,
        *,
        org_id: str,
        request_id: str,
        approver: SessionAssurance,
        required_assurance: str = "TOTP",
    ) -> IdentityFourEyesRequest:
        if approver.org_id != org_id:
            raise forbidden("CROSS_TENANT", "Approver is not in this organization.")
        await self._assert_human_privileged(org_id, approver.user_id)
        if approver.rank() < ASSURANCE_RANK.get(required_assurance, 0):
            raise EnterpriseError(
                "AUTHENTICATION_ASSURANCE_TOO_LOW",
                "Approver assurance is too low for four-eyes approval.",
                403,
            )
        now = datetime.now(UTC).isoformat()
        async with self.engine.raw.begin() as conn:
            row = (
                await conn.execute(
                    select(identity_four_eyes_requests).where(
                        identity_four_eyes_requests.c.id == request_id,
                        identity_four_eyes_requests.c.org_id == org_id,
                    )
                )
            ).fetchone()
            if row is None:
                raise EnterpriseError("FOUR_EYES_REQUIRED", "Four-eyes request not found.", 404)
            if row.requester_user_id == approver.user_id:
                raise EnterpriseError(
                    "SELF_APPROVAL_BLOCKED", "Requester cannot approve their own request.", 403
                )
            await self._assert_principal_active(conn, row.requester_user_id, org_id)
            await self._assert_principal_active(conn, approver.user_id, org_id)
            if row.status == FourEyesState.EXPIRED.value or now >= row.expires_at:
                await conn.execute(
                    update(identity_four_eyes_requests)
                    .where(identity_four_eyes_requests.c.id == request_id)
                    .values(status=FourEyesState.EXPIRED.value)
                )
                raise EnterpriseError("FOUR_EYES_EXPIRED", "Four-eyes request expired.", 403)
            if row.status != FourEyesState.PENDING.value:
                raise EnterpriseError("FOUR_EYES_REPLAY", "Four-eyes request is not pending.", 403)
            await conn.execute(
                update(identity_four_eyes_requests)
                .where(
                    identity_four_eyes_requests.c.id == request_id,
                    identity_four_eyes_requests.c.status == FourEyesState.PENDING.value,
                )
                .values(
                    status=FourEyesState.APPROVED.value,
                    approver_user_id=approver.user_id,
                    approved_at=now,
                )
            )
        return IdentityFourEyesRequest(
            id=request_id,
            org_id=org_id,
            requester_user_id=row.requester_user_id,
            action=row.action,
            digest=row.action_digest,
            status=FourEyesState.APPROVED.value,
            created_at=row.created_at,
            expires_at=row.expires_at,
            approver_user_id=approver.user_id,
            parameters=json.loads(row.parameters_json),
        )

    async def consume(
        self,
        *,
        org_id: str,
        request_id: str,
        action: str,
        parameters: dict[str, Any],
    ) -> IdentityFourEyesRequest:
        digest = canonical_action_digest(action, parameters)
        now = datetime.now(UTC).isoformat()
        async with self.engine.raw.begin() as conn:
            row = (
                await conn.execute(
                    select(identity_four_eyes_requests).where(
                        identity_four_eyes_requests.c.id == request_id,
                        identity_four_eyes_requests.c.org_id == org_id,
                    )
                )
            ).fetchone()
            if row is None:
                raise EnterpriseError("FOUR_EYES_REQUIRED", "Four-eyes request not found.", 404)
            if now >= row.expires_at:
                await conn.execute(
                    update(identity_four_eyes_requests)
                    .where(identity_four_eyes_requests.c.id == request_id)
                    .values(status=FourEyesState.EXPIRED.value)
                )
                raise EnterpriseError("FOUR_EYES_EXPIRED", "Four-eyes request expired.", 403)
            if row.status == FourEyesState.CONSUMED.value:
                raise EnterpriseError(
                    "FOUR_EYES_REPLAY", "Four-eyes approval already consumed.", 403
                )
            if row.status != FourEyesState.APPROVED.value:
                raise EnterpriseError("FOUR_EYES_REQUIRED", "Four-eyes approval is required.", 403)
            if row.action != action or row.action_digest != digest:
                raise EnterpriseError(
                    "FOUR_EYES_MUTATION", "Approved action parameters changed.", 403
                )
            await self._assert_principal_active(conn, row.requester_user_id, org_id)
            if row.approver_user_id:
                await self._assert_principal_active(conn, row.approver_user_id, org_id)
            result = await conn.execute(
                update(identity_four_eyes_requests)
                .where(
                    identity_four_eyes_requests.c.id == request_id,
                    identity_four_eyes_requests.c.status == FourEyesState.APPROVED.value,
                )
                .values(status=FourEyesState.CONSUMED.value, consumed_at=now)
            )
            if (result.rowcount or 0) != 1:
                raise EnterpriseError(
                    "FOUR_EYES_REPLAY", "Four-eyes approval already consumed.", 403
                )
        return IdentityFourEyesRequest(
            id=request_id,
            org_id=org_id,
            requester_user_id=row.requester_user_id,
            action=row.action,
            digest=row.action_digest,
            status=FourEyesState.CONSUMED.value,
            created_at=row.created_at,
            expires_at=row.expires_at,
            approver_user_id=row.approver_user_id,
        )

    async def _assert_human_privileged(self, org_id: str, user_id: str) -> None:
        async with self.engine.raw.connect() as conn:
            await self._assert_principal_active(conn, user_id, org_id)
            sa = (
                await conn.execute(
                    select(enterprise_service_accounts).where(
                        enterprise_service_accounts.c.org_id == org_id,
                        enterprise_service_accounts.c.created_by_user_id == user_id,
                        enterprise_service_accounts.c.id == user_id,
                    )
                )
            ).fetchone()
            sa_id = (
                await conn.execute(
                    select(enterprise_service_accounts).where(
                        enterprise_service_accounts.c.id == user_id
                    )
                )
            ).fetchone()
            if sa is not None or sa_id is not None:
                raise EnterpriseError(
                    "SELF_APPROVAL_BLOCKED", "Service accounts cannot satisfy four-eyes.", 403
                )

    async def _assert_principal_active(self, conn: Any, user_id: str, org_id: str) -> None:
        user = (await conn.execute(select(web_users).where(web_users.c.id == user_id))).fetchone()
        if user is None or user.disabled or user.verification_status == "SUSPENDED":
            raise EnterpriseError("FOUR_EYES_PRINCIPAL_REVOKED", "Principal is not active.", 403)
        membership = (
            await conn.execute(
                select(web_memberships).where(
                    web_memberships.c.user_id == user_id,
                    web_memberships.c.org_id == org_id,
                    web_memberships.c.status == "ACTIVE",
                )
            )
        ).fetchone()
        if membership is None:
            raise forbidden(
                "CROSS_TENANT", "Principal is not an active member of this organization."
            )
        if membership.role not in PRIVILEGED_APPROVER_ROLES:
            raise EnterpriseError("FORBIDDEN", "Insufficient role for four-eyes.", 403)
