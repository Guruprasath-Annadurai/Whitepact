# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Durable single-use permits, serialized against tenant revocation updates.

Consumption is the admission linearization point, not an exactly-once guarantee
for external side effects. A later revocation cannot undo an admitted operation.
"""

from datetime import UTC, datetime

from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from responsibleai.db.engine import DatabaseEngine
from responsibleai.db.engine import governance_execution_nonces as nonces
from responsibleai.db.engine import organizations
from responsibleai.db.revocation_epoch_repository import lock_epoch
from responsibleai.rbac.models import GovernanceStatus


class NonceAlreadyConsumedError(Exception):
    """The permit was already admitted by this or another replica."""


class StaleRevocationEpochError(Exception):
    """Authority changed since the permit was evaluated."""


class OrganizationNotGovernableError(Exception):
    """The organization is missing or not ACTIVE at admission."""


class ExecutionNonceRepository:
    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def consume(
        self, nonce: str, *, authorization_id: str, organization_id: str, expected_epoch: int
    ) -> None:
        if not nonce or not authorization_id or not organization_id or expected_epoch < 0:
            raise ValueError("An explicit tenant-bound permit and epoch are required")
        try:
            async with self._engine.raw.begin() as conn:
                # Canonical lock order: organizations before epochs.
                status_stmt = select(organizations.c.governance_status).where(
                    organizations.c.id == organization_id
                )
                if conn.dialect.name == "postgresql":
                    status_stmt = status_stmt.with_for_update()
                status = (await conn.execute(status_stmt)).scalar_one_or_none()
                if status != GovernanceStatus.ACTIVE.value:
                    raise OrganizationNotGovernableError(
                        "Organization is not ACTIVE for governed execution"
                    )
                current = await lock_epoch(conn, organization_id)
                if current != expected_epoch:
                    raise StaleRevocationEpochError("Permit revocation epoch is stale")
                await conn.execute(
                    insert(nonces).values(
                        nonce=nonce,
                        authorization_id=authorization_id,
                        organization_id=organization_id,
                        consumed_at=datetime.now(UTC).isoformat(),
                    )
                )
        except IntegrityError as exc:
            # Do not mislabel missing-tenant or other integrity failures as replay.
            async with self._engine.raw.connect() as conn:
                found = await conn.scalar(select(nonces.c.nonce).where(nonces.c.nonce == nonce))
            if found is not None:
                raise NonceAlreadyConsumedError("Permit nonce already consumed") from exc
            raise
