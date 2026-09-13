# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Just-In-Time (JIT) Privileged Access Service."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, insert, select, update

from responsibleai.db.engine import DatabaseEngine, iam_jit_grants
from responsibleai.iam.enums import JitGrantStatus, PrivilegedAction
from responsibleai.iam.errors import JitGrantInvalidError
from responsibleai.iam.models import JitGrant
from responsibleai.rbac.models import Role


class JitAccessService:
    """Manages time-bounded, purpose-bound, dynamically evaluated JIT privileged grants."""

    def __init__(self, db: DatabaseEngine) -> None:
        self.db = db

    async def request_jit_access(
        self,
        *,
        org_id: str,
        principal_id: str,
        target_role: Role,
        allowed_actions: list[PrivilegedAction],
        justification: str,
        ttl_minutes: int = 60,
    ) -> JitGrant:
        """Request temporary privilege elevation."""
        if ttl_minutes <= 0 or ttl_minutes > 480:  # 8 hours max
            raise ValueError("JIT access TTL must be between 1 and 480 minutes (8 hours max).")

        if target_role == Role.OWNER:
            raise ValueError("JIT access cannot elevate to OWNER role.")

        if any(
            a in {PrivilegedAction.TRANSFER_ROOT_AUTHORITY, PrivilegedAction.RECOVER_ROOT_AUTHORITY, PrivilegedAction.DESTROY_TENANT}
            for a in allowed_actions
        ):
            raise ValueError("JIT access cannot grant sovereign root operations.")

        grant_id = f"jit_{uuid.uuid4().hex}"
        now = datetime.now(UTC)
        expires_at = (now + timedelta(minutes=ttl_minutes)).isoformat()

        grant = JitGrant(
            id=grant_id,
            org_id=org_id,
            principal_id=principal_id,
            target_role=target_role,
            allowed_actions=allowed_actions,
            justification=justification,
            status=JitGrantStatus.REQUESTED,
            requested_at=now.isoformat(),
            expires_at=expires_at,
        )

        async with self.db.raw.begin() as conn:
            await conn.execute(
                insert(iam_jit_grants).values(
                    id=grant.id,
                    org_id=grant.org_id,
                    principal_id=grant.principal_id,
                    target_role=grant.target_role.value,
                    allowed_actions_json=json.dumps([a.value for a in grant.allowed_actions]),
                    justification=grant.justification,
                    status=grant.status.value,
                    requested_at=grant.requested_at,
                    approved_at=None,
                    approver_principal_id=None,
                    expires_at=grant.expires_at,
                    revoked_at=None,
                )
            )

        return grant

    async def approve_jit_access(
        self,
        *,
        org_id: str,
        grant_id: str,
        approver_principal_id: str,
    ) -> JitGrant:
        """Approve and activate a JIT grant. Rejects self-approval."""
        now = datetime.now(UTC).isoformat()

        async with self.db.raw.begin() as conn:
            stmt = select(iam_jit_grants).where(
                and_(
                    iam_jit_grants.c.id == grant_id,
                    iam_jit_grants.c.org_id == org_id,
                )
            )
            row = (await conn.execute(stmt)).first()
            if not row:
                raise JitGrantInvalidError(f"JIT grant {grant_id!r} not found.")

            rec = dict(row._mapping)

            # Invariant: requester cannot approve their own JIT elevation
            if rec["principal_id"] == approver_principal_id:
                raise ValueError("Requester cannot approve their own JIT grant.")

            if rec["status"] != JitGrantStatus.REQUESTED.value:
                raise JitGrantInvalidError(f"JIT grant is in state {rec['status']}, cannot approve.")

            await conn.execute(
                update(iam_jit_grants)
                .where(iam_jit_grants.c.id == grant_id)
                .values(
                    status=JitGrantStatus.ACTIVE.value,
                    approved_at=now,
                    approver_principal_id=approver_principal_id,
                )
            )

            actions = [PrivilegedAction(a) for a in json.loads(rec["allowed_actions_json"])]
            return JitGrant(
                id=grant_id,
                org_id=org_id,
                principal_id=rec["principal_id"],
                target_role=Role(rec["target_role"]),
                allowed_actions=actions,
                justification=rec["justification"],
                status=JitGrantStatus.ACTIVE,
                requested_at=rec["requested_at"],
                approved_at=now,
                approver_principal_id=approver_principal_id,
                expires_at=rec["expires_at"],
            )

    async def revoke_jit_access(self, *, org_id: str, grant_id: str) -> bool:
        """Prematurely revoke an active JIT grant."""
        now = datetime.now(UTC).isoformat()
        async with self.db.raw.begin() as conn:
            res = await conn.execute(
                update(iam_jit_grants)
                .where(
                    and_(
                        iam_jit_grants.c.id == grant_id,
                        iam_jit_grants.c.org_id == org_id,
                    )
                )
                .values(status=JitGrantStatus.REVOKED.value, revoked_at=now)
            )
            return (res.rowcount or 0) > 0
