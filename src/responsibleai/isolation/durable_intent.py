# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Runtime ownership fencing. The journal is restrictive, never execution authority.

M13 uses a conservative global restart fence. Incomplete work from any previous
process generation prevents automatic new execution. This is not a cluster-wide
daemon sweep or an automatic privileged recovery API.
"""

import hashlib
import json
import os
import re
import subprocess
import uuid

from sqlalchemy import select

from responsibleai.db.containment_repository import ContainmentAdmissionError, ContainmentRepository
from responsibleai.db.engine import runtime_containment_records
from responsibleai.enterprise.runtime import get_enterprise_engine
from responsibleai.isolation.mode import unisolated_execution_allowed

_OWNER_PID = os.getpid()
_OWNER_GENERATION = uuid.uuid4().hex


def process_generation() -> str:
    global _OWNER_PID, _OWNER_GENERATION
    if _OWNER_PID != os.getpid():
        _OWNER_PID = os.getpid()
        _OWNER_GENERATION = uuid.uuid4().hex
    return _OWNER_GENERATION


def fence_process_generation() -> None:
    """Make every still-nonterminal association stale, even if a DB write fails.

    This only restricts admission. It cannot clear uncertainty or issue authority.
    The old durable intents survive restart even if Store B cannot be updated.
    """
    global _OWNER_GENERATION
    _OWNER_GENERATION = uuid.uuid4().hex


def required_journal() -> ContainmentRepository | None:
    # Existing explicit local-only prototype escape, never production. No new
    # production bypass flag and no fallback on missing schema/database errors.
    if unisolated_execution_allowed():
        return None
    engine = get_enterprise_engine()
    if engine.raw.dialect.name != "postgresql":
        raise ContainmentAdmissionError("Hosted container execution requires a PostgreSQL journal")
    return ContainmentRepository(engine)


def daemon_identity(docker_cmd: str) -> str:
    result = subprocess.run(
        [docker_cmd, "info", "--format", "{{.ID}}"],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    identity = result.stdout.strip()
    if not identity or len(identity) > 128 or not re.fullmatch(r"[A-Za-z0-9:_-]+", identity):
        raise ContainmentAdmissionError("Docker daemon identity is unavailable")
    return identity


async def assert_runtime_inventory(
    repository: ContainmentRepository, docker_cmd: str, backend_identity: str
) -> None:
    """Unknown managed-looking work fences admission; it is NEVER removed here."""
    import asyncio

    generation = process_generation()
    await repository.assert_admitted(owner_generation=generation)
    async with repository._engine.raw.connect() as conn:
        rows = (
            (
                await conn.execute(
                    select(runtime_containment_records).where(
                        runtime_containment_records.c.owner_generation == generation,
                        runtime_containment_records.c.backend_identity == backend_identity,
                        runtime_containment_records.c.state == "ACTIVE",
                    )
                )
            )
            .mappings()
            .all()
        )
    owned = {row["container_id"]: row for row in rows}
    result = await asyncio.to_thread(
        subprocess.run,
        [docker_cmd, "ps", "--all", "--no-trunc", "--format", "{{json .}}"],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    for line in result.stdout.splitlines():
        record = json.loads(line)
        labels = record.get("Labels", "")
        name = record.get("Names", "")
        cid = record.get("ID", "")
        if not isinstance(labels, str) or not isinstance(name, str) or not isinstance(cid, str):
            raise ContainmentAdmissionError("Invalid Docker inventory response")
        suspected = "io.whitepact.execution=" in labels or name.startswith("wp_iso_")
        if suspected and cid not in owned:
            # A name/label is only reason to quarantine, never proof of ownership
            # or permission to kill a possibly foreign container.
            raise ContainmentAdmissionError(
                "Unattributed runtime workload requires operator reconciliation"
            )
        if cid in owned:
            row = owned[cid]
            actual = dict(part.split("=", 1) for part in labels.split(",") if "=" in part)
            if (
                actual.get("io.whitepact.organization")
                != hashlib.sha256(row["organization_id"].encode()).hexdigest()
                or actual.get("io.whitepact.execution") != row["execution_id"]
                or actual.get("io.whitepact.generation") != generation
                or name != row["expected_container_name"]
            ):
                raise ContainmentAdmissionError(
                    "Runtime ownership labels conflict with durable association"
                )
