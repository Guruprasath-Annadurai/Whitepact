# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Four-Eyes Administration & Dual Custody Service."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, insert, select, update

from responsibleai.db.engine import DatabaseEngine, iam_four_eyes_requests
from responsibleai.iam.enums import FourEyesStatus, PrivilegedAction
from responsibleai.iam.errors import (
    FourEyesRequiredError,
    SelfApprovalBlockedError,
)
from responsibleai.iam.models import FourEyesRequest, canonical_hash


class FourEyesService:
    """Enforces dual-custody approval: requester != approver, independent credentials."""

    def __init__(self, db: DatabaseEngine) -> None:
        self.db = db

    async def submit_four_eyes_request(
        self,
        *,
        org_id: str,
        requester_principal_id: str,
        action: PrivilegedAction,
        target_resource_id: str | None = None,
        parameters: dict[str, Any] | None = None,
        ttl_minutes: int = 120,
    ) -> FourEyesRequest:
        """Submit a critical operation request awaiting independent approval."""
        req_id = f"fe_{uuid.uuid4().hex}"
        now = datetime.now(UTC)
        expires_at = (now + timedelta(minutes=ttl_minutes)).isoformat()
        params = parameters or {}
        params_json = json.dumps(params, sort_keys=True)

        digest_payload = {
            "req_id": req_id,
            "org_id": org_id,
            "requester": requester_principal_id,
            "action": action.value,
            "target": target_resource_id,
            "params": params,
        }
        digest = canonical_hash(digest_payload)

        async with self.db.raw.begin() as conn:
            await conn.execute(
                insert(iam_four_eyes_requests).values(
                    id=req_id,
                    org_id=org_id,
                    requester_principal_id=requester_principal_id,
                    action=action.value,
                    target_resource_id=target_resource_id,
                    parameters_json=params_json,
                    request_digest=digest,
                    status=FourEyesStatus.PENDING.value,
                    approver_principal_id=None,
                    approval_time=None,
                    rejection_reason=None,
                    executed_at=None,
                    created_at=now.isoformat(),
                    expires_at=expires_at,
                )
            )

        return FourEyesRequest(
            id=req_id,
            org_id=org_id,
            requester_principal_id=requester_principal_id,
            action=action,
            target_resource_id=target_resource_id,
            parameters_json=params_json,
            request_digest=digest,
            status=FourEyesStatus.PENDING,
            created_at=now.isoformat(),
            expires_at=expires_at,
        )

    async def approve_four_eyes_request(
        self,
        *,
        org_id: str,
        request_id: str,
        approver_principal_id: str,
    ) -> FourEyesRequest:
        """Approve a dual-custody request. Strictly rejects self-approval."""
        now = datetime.now(UTC).isoformat()

        async with self.db.raw.begin() as conn:
            stmt = select(iam_four_eyes_requests).where(
                and_(
                    iam_four_eyes_requests.c.id == request_id,
                    iam_four_eyes_requests.c.org_id == org_id,
                )
            )
            row = (await conn.execute(stmt)).first()
            if not row:
                raise FourEyesRequiredError("Four-Eyes request not found.")

            rec = dict(row._mapping)

            # Invariant: Self-approval is strictly prohibited!
            if rec["requester_principal_id"] == approver_principal_id:
                raise SelfApprovalBlockedError("Requester cannot approve their own Four-Eyes request.")

            if rec["status"] != FourEyesStatus.PENDING.value:
                raise ValueError(f"Request is in status {rec['status']}, cannot approve.")

            if now >= rec["expires_at"]:
                raise ValueError("Four-Eyes request has expired.")

            await conn.execute(
                update(iam_four_eyes_requests)
                .where(iam_four_eyes_requests.c.id == request_id)
                .values(
                    status=FourEyesStatus.APPROVED.value,
                    approver_principal_id=approver_principal_id,
                    approval_time=now,
                )
            )

            return FourEyesRequest(
                id=request_id,
                org_id=org_id,
                requester_principal_id=rec["requester_principal_id"],
                action=PrivilegedAction(rec["action"]),
                target_resource_id=rec["target_resource_id"],
                parameters_json=rec["parameters_json"],
                request_digest=rec["request_digest"],
                status=FourEyesStatus.APPROVED,
                approver_principal_id=approver_principal_id,
                approval_time=now,
                created_at=rec["created_at"],
                expires_at=rec["expires_at"],
            )
