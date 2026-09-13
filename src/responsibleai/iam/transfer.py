# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Sovereign Voluntary Root Authority Transfer Service."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, select, update

from responsibleai.db.engine import (
    DatabaseEngine,
    trust_fabric_trust_roots,
)
from responsibleai.db.revocation_epoch_repository import bump_epoch_on_connection
from responsibleai.iam.errors import (
    PrivilegedAccessDeniedError,
    SelfApprovalBlockedError,
)
from responsibleai.iam.session import SessionService
from responsibleai.trust_fabric.models import compute_digest


class SovereignTransferService:
    """Customer-controlled voluntary root authority transfer with anti-replay and anti-self-approval."""

    def __init__(self, db: DatabaseEngine) -> None:
        self.db = db
        self.session_service = SessionService(db)
        self._consumed_transfer_tokens: set[str] = set()

    def generate_transfer_token(self) -> str:
        """Generate a single-use voluntary root transfer authorization token."""
        return f"wp_xfer_{secrets.token_urlsafe(32)}"

    async def transfer_root_authority(
        self,
        *,
        org_id: str,
        current_root_principal_id: str,
        new_root_principal_id: str,
        new_root_public_key: str,
        transfer_token: str,
        context_data: dict[str, Any] | None = None,
    ) -> bool:
        """Atomically execute voluntary root handover to a new sovereign principal."""
        # 1. Anti-self-transfer invariant
        if current_root_principal_id == new_root_principal_id:
            raise SelfApprovalBlockedError("Cannot transfer root authority to the existing root principal.")

        # 2. Anti-replay defense
        if not transfer_token or transfer_token in self._consumed_transfer_tokens:
            raise PrivilegedAccessDeniedError("Transfer authorization token has already been consumed or is invalid.")

        now = datetime.now(UTC).isoformat()

        async with self.db.raw.begin() as conn:
            # 3. Verify that current_root_principal_id is currently the active root
            root_stmt = select(trust_fabric_trust_roots).where(
                and_(
                    trust_fabric_trust_roots.c.org_id == org_id,
                    trust_fabric_trust_roots.c.status == "ACTIVE",
                )
            )
            root_row = (await conn.execute(root_stmt)).first()
            if not root_row:
                raise PrivilegedAccessDeniedError("No active sovereign root authority found for tenant.")

            if root_row.root_principal_id != current_root_principal_id:
                raise PrivilegedAccessDeniedError(
                    f"Caller {current_root_principal_id!r} is not the active sovereign root."
                )

            # 4. Atomically update root record to new root
            payload = {
                "id": root_row.id,
                "org_id": org_id,
                "root_principal_id": new_root_principal_id,
                "root_public_key": new_root_public_key,
                "established_at": now,
                "key_algorithm": "Ed25519",
            }
            canonical_digest = compute_digest(payload)

            await conn.execute(
                update(trust_fabric_trust_roots)
                .where(trust_fabric_trust_roots.c.id == root_row.id)
                .values(
                    root_principal_id=new_root_principal_id,
                    root_public_key=new_root_public_key,
                    key_algorithm="Ed25519",
                    established_at=now,
                    canonical_digest=canonical_digest,
                )
            )

            # 5. Bump revocation epochs
            await bump_epoch_on_connection(conn, org_id, scope="iam_session")
            await bump_epoch_on_connection(conn, org_id, scope="governance")

        # 6. Consume transfer token
        self._consumed_transfer_tokens.add(transfer_token)

        # 7. Invalidate all active sessions of the former root principal
        await self.session_service.revoke_all_principal_sessions(
            org_id=org_id, principal_id=current_root_principal_id
        )

        return True
