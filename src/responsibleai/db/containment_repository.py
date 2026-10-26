# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Restrictive pre-create journal; never grants authority or infers containment.

A new process cannot adopt a previous generation's incomplete execution. No
expiry, PID check, missing file or name-based scan clears this journal.
"""

import re
from datetime import UTC, datetime

from sqlalchemy import and_, insert, or_, select, update

from responsibleai.db.engine import DatabaseEngine, organizations, runtime_containment_records


class ContainmentAdmissionError(RuntimeError):
    """Durable containment uncertainty or unavailable storage denies admission."""


class ContainmentGenerationConflictError(ContainmentAdmissionError):
    """A stale caller or incompatible transition cannot modify ownership."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _required(value: str, maximum: int) -> None:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > maximum:
        raise ValueError("An exact nonempty bounded association is required")


class ContainmentRepository:
    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    @staticmethod
    def _blockers(owner_generation: str):
        c = runtime_containment_records.c
        return or_(
            c.state == "UNRESOLVED",
            and_(c.state != "CONTAINED", c.owner_generation != owner_generation),
        )

    async def assert_admitted(self, *, owner_generation: str) -> None:
        """Conservative global restart fence, not a single-host absence claim."""
        _required(owner_generation, 64)
        async with self._engine.raw.connect() as conn:
            blocker = await conn.scalar(
                select(runtime_containment_records.c.execution_id)
                .where(self._blockers(owner_generation))
                .limit(1)
            )
            if blocker is not None:
                raise ContainmentAdmissionError("Durable containment ownership is unresolved")

    async def begin(
        self,
        *,
        execution_id: str,
        organization_id: str,
        owner_generation: str,
        backend_identity: str,
        authorization_id: str,
        action_digest: str,
        admission_epoch: int,
        expected_container_name: str,
    ) -> None:
        for value, maximum in (
            (execution_id, 64),
            (organization_id, 36),
            (owner_generation, 64),
            (backend_identity, 128),
            (authorization_id, 64),
            (expected_container_name, 128),
        ):
            _required(value, maximum)
        if re.fullmatch(r"[0-9a-f]{64}", action_digest) is None:
            raise ValueError("A canonical action digest is required")
        if type(admission_epoch) is not int or admission_epoch < 0:
            raise ValueError("A nonnegative exact epoch is required")
        async with self._engine.raw.begin() as conn:
            # Serialize pre-create associations across organizations/processes.
            # No row lock can serialize an initially empty journal. PostgreSQL's
            # transaction lock protects the global fence and insert together.
            if conn.dialect.name == "postgresql":
                from sqlalchemy import text

                await conn.execute(text("SELECT pg_advisory_xact_lock(871634592)"))
            organization = select(organizations.c.governance_status).where(
                organizations.c.id == organization_id
            )
            if conn.dialect.name == "postgresql":
                organization = organization.with_for_update()
            if await conn.scalar(organization) != "ACTIVE":
                raise ContainmentAdmissionError("A real ACTIVE organization is required")
            if (
                await conn.scalar(
                    select(runtime_containment_records.c.execution_id)
                    .where(self._blockers(owner_generation))
                    .limit(1)
                )
                is not None
            ):
                raise ContainmentAdmissionError(
                    "An unresolved or prior generation owns runtime work"
                )
            now = _now()
            await conn.execute(
                insert(runtime_containment_records).values(
                    execution_id=execution_id,
                    organization_id=organization_id,
                    owner_generation=owner_generation,
                    backend_identity=backend_identity,
                    authorization_id=authorization_id,
                    action_digest=action_digest,
                    admission_epoch=admission_epoch,
                    expected_container_name=expected_container_name,
                    container_id=None,
                    state="PREPARING",
                    created_at=now,
                    updated_at=now,
                )
            )

    async def acknowledge(self, execution_id: str, owner_generation: str, cid: str) -> None:
        if re.fullmatch(r"[0-9a-f]{64}", cid) is None:
            raise ValueError("An exact immutable container ID is required")
        await self._transition(execution_id, owner_generation, "ACTIVE", cid=cid)

    async def assert_startable(self, execution_id: str, generation: str, cid: str) -> None:
        from responsibleai.db.revocation_epoch_repository import current_epoch_on_connection

        await self.assert_admitted(owner_generation=generation)
        c = runtime_containment_records.c
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(c.organization_id, c.admission_epoch).where(
                        c.execution_id == execution_id,
                        c.owner_generation == generation,
                        c.state == "ACTIVE",
                        c.container_id == cid,
                    )
                )
            ).first()
            if row is None:
                raise ContainmentAdmissionError("Execution creation has not been acknowledged")
            status = await conn.scalar(
                select(organizations.c.governance_status).where(
                    organizations.c.id == row.organization_id
                )
            )
            epoch = await current_epoch_on_connection(conn, row.organization_id)
            if status != "ACTIVE" or epoch.epoch != row.admission_epoch:
                raise ContainmentAdmissionError(
                    "Organization authority changed before container start"
                )

    async def finish(self, execution_id: str, owner_generation: str) -> None:
        """Trusted executor calls only after independent exact-CID cleanup proof."""
        await self._transition(execution_id, owner_generation, "CONTAINED")

    async def mark_unresolved(self, execution_id: str, owner_generation: str) -> None:
        await self._transition(execution_id, owner_generation, "UNRESOLVED")

    async def _transition(
        self, execution_id: str, generation: str, state: str, cid: str | None = None
    ) -> None:
        _required(execution_id, 64)
        _required(generation, 64)
        c = runtime_containment_records.c
        predicates = [c.execution_id == execution_id, c.owner_generation == generation]
        values = {"state": state, "updated_at": _now()}
        if state == "ACTIVE":
            if cid is None:
                raise ValueError("A creation acknowledgement is required")
            predicates += [c.state == "PREPARING", c.container_id.is_(None)]
            values["container_id"] = cid
        elif state == "CONTAINED":
            predicates += [c.state.in_(("ACTIVE", "UNRESOLVED")), c.container_id.is_not(None)]
        else:
            predicates += [c.state != "CONTAINED"]
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                update(runtime_containment_records).where(*predicates).values(**values)
            )
            if result.rowcount != 1:
                raise ContainmentGenerationConflictError(
                    "Unknown execution, stale generation or invalid transition"
                )
