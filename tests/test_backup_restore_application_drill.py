# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""A restore drill on real application state, not on a one-row marker table.

``tests/test_gate2_remediation.py`` proves the backup and restore *scripts* are safe (source kept
until the copy verifies, corrupt artifacts refused). It does not show that what comes back is a
working, still-safe WhitePact database. This does, on a real migrated schema with a real tenant, key,
approval, executed effect and evidence chain:

* the restored copy holds the backup-time state and none of the later state;
* the schema is at the migration head;
* the evidence hash chain still verifies;
* the spent execution nonce is still spent (replay after a restore must stay refused);
* a key revoked before the backup is still revoked after it, a live key still authenticates.

It uses the real ``scripts/backup-postgres.sh`` and ``scripts/restore-postgres.sh``. Timings are
printed as a local measurement for the drill register, not as an objective.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select, text

from responsibleai.db import EvidenceRepository, create_engine
from responsibleai.db.engine import governance_execution_nonces
from responsibleai.db.execution_nonce_repository import (
    ExecutionNonceRepository,
    NonceAlreadyConsumedError,
)
from responsibleai.db.org_repository import OrgRepository
from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository
from tests import test_v1_exactly_one_effect as _effect_tests
from tests.test_v1_customer_journey import _quorum_approve_and_execute
from tests.test_v1_exactly_one_effect import ADMIN_EMAIL, OWNER_EMAIL, _call, _prepare_org

# The fixtures live in the journey test module; re-export them under their own names so pytest
# resolves them here without a redefinition.
journey_client = _effect_tests.journey_client
pg_url = _effect_tests.pg_url

ROOT = Path(__file__).resolve().parents[1]
BACKUP = ROOT / "scripts" / "backup-postgres.sh"
RESTORE = ROOT / "scripts" / "restore-postgres.sh"
RELATIONS = "organizations,org_api_keys,governance_evidence,governance_execution_nonces"
COUNTED = (
    "organizations",
    "org_api_keys",
    "governance_evidence",
    "governance_execution_nonces",
    "governance_approvals",
)


def _pg_env(url: str, database: str) -> dict[str, str]:
    parsed = urlparse(url)
    env = os.environ.copy()
    env.update(
        PGHOST=parsed.hostname or "127.0.0.1",
        PGPORT=str(parsed.port or 5432),
        PGUSER=parsed.username or "",
        PGPASSWORD=parsed.password or "",
        PGDATABASE=database,
        PYTHONPATH=str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", ""),
    )
    return env


def _with_database(url: str, database: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(path=f"/{database}"))


async def _counts(url: str) -> dict[str, int]:
    engine = create_engine(url)
    await engine.init(auto_create_tables=False)
    try:
        async with engine.raw.connect() as conn:
            return {
                table: int((await conn.execute(text(f"SELECT count(*) FROM {table}"))).scalar())
                for table in COUNTED
            }
    finally:
        await engine.close()


async def _drop(url: str, database: str) -> None:
    import asyncpg

    admin = _with_database(url, "postgres").replace("+asyncpg", "")
    conn = await asyncpg.connect(admin)
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)')
    finally:
        await conn.close()


async def test_restored_database_keeps_security_state_and_excludes_later_state(
    journey_client, monkeypatch, seed_runtime_authority, tmp_path
) -> None:
    client, pg = journey_client
    source_db = urlparse(pg).path.lstrip("/")
    org_id, raw = await _prepare_org(client, monkeypatch, seed_runtime_authority, pg)

    # Real state: one approved + executed effect (spends a nonce, writes evidence) ...
    pending = await _call(client, raw)
    approval_id = pending.json()["approval_id"]
    executed = await _quorum_approve_and_execute(
        client, approval_id, owner_email=OWNER_EMAIL, admin_email=ADMIN_EMAIL
    )
    assert executed.get("execution_status") is not None

    # ... and a second key that is revoked before the backup.
    engine = create_engine(pg)
    await engine.init(auto_create_tables=False)
    async with engine.raw.begin() as conn:
        await conn.execute(
            text("UPDATE organizations SET plan = 'ENTERPRISE' WHERE id = :i"), {"i": org_id}
        )
    created = await client.post(
        "/api/v1/web/api-keys",
        headers={"X-WP-CSRF": client.cookies["wp_csrf"]},
        json={"name": "doomed", "environment": "test", "scopes": ["governance:read"]},
    )
    assert created.status_code == 201, created.text
    doomed_raw = created.json()["api_key"]
    doomed_ctx = await OrgRepository(engine).authenticate(doomed_raw)
    assert doomed_ctx is not None
    assert await OrgRepository(engine).revoke_key(doomed_ctx.key_id, org_id=org_id) is True
    await engine.close()

    before_backup = await _counts(pg)
    assert before_backup["governance_execution_nonces"] >= 1
    assert before_backup["governance_evidence"] >= 1

    secret = Fernet.generate_key().decode("ascii")
    started = time.perf_counter()
    backup = subprocess.run(  # noqa: S603
        ["bash", str(BACKUP), str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
        env={
            **_pg_env(pg, source_db),
            "WHITEPACT_BACKUP_LOCAL": "1",
            "WHITEPACT_BACKUP_ENCRYPTION_KEY": secret,
            "WHITEPACT_BACKUP_REQUIRED_RELATIONS": RELATIONS,
        },
    )
    backup_seconds = time.perf_counter() - started
    assert backup.returncode == 0, backup.stdout + backup.stderr
    artifact = next(tmp_path.glob("*.sql.gz.enc"))

    # State created AFTER the backup must not appear in the restored copy.
    later = await _call(client, raw)
    assert later.json()["error"] == "governance_approval_required"
    after_backup = await _counts(pg)
    assert after_backup["governance_approvals"] == before_backup["governance_approvals"] + 1

    started = time.perf_counter()
    restored = subprocess.run(  # noqa: S603
        ["bash", str(RESTORE), str(artifact)],
        check=False,
        capture_output=True,
        text=True,
        env={
            **_pg_env(pg, source_db),
            "WHITEPACT_BACKUP_ENCRYPTION_KEY": secret,
            "WHITEPACT_RESTORE_LOCAL": "1",
        },
    )
    restore_seconds = time.perf_counter() - started
    assert restored.returncode == 0, restored.stdout + restored.stderr
    staging = ""
    for line in restored.stdout.splitlines():
        marker = "Staging restore verified:"
        if marker in line:
            staging = line.split(marker, 1)[1].strip()
    assert staging.startswith("wp_restore_"), restored.stdout

    restored_url = _with_database(pg, staging)
    try:
        # 1. Backup-time state, not later state; the source was not touched.
        assert await _counts(restored_url) == before_backup
        assert await _counts(pg) == after_backup

        engine = create_engine(restored_url)
        await engine.init(auto_create_tables=False)
        try:
            # 2. Schema at the migration head.
            async with engine.raw.connect() as conn:
                restored_version = (
                    await conn.execute(text("SELECT version_num FROM alembic_version"))
                ).scalar()
            source_engine = create_engine(pg)
            await source_engine.init(auto_create_tables=False)
            try:
                async with source_engine.raw.connect() as conn:
                    source_version = (
                        await conn.execute(text("SELECT version_num FROM alembic_version"))
                    ).scalar()
            finally:
                await source_engine.close()
            assert restored_version == source_version

            # 3. The evidence chain still verifies.
            assert await EvidenceRepository(engine).verify_chain(org_id) is True

            # 4. A spent nonce is still spent after the restore.
            async with engine.raw.connect() as conn:
                nonce_row = (
                    await conn.execute(select(governance_execution_nonces).limit(1))
                ).fetchone()
            assert nonce_row is not None
            epoch = (await RevocationEpochRepository(engine).current(org_id)).epoch
            with pytest.raises(NonceAlreadyConsumedError):
                await ExecutionNonceRepository(engine).consume(
                    nonce_row.nonce,
                    authorization_id=nonce_row.authorization_id,
                    organization_id=org_id,
                    expected_epoch=epoch,
                )

            # 5. Revocation survived; a live key still works.
            repo = OrgRepository(engine)
            assert await repo.authenticate(doomed_raw) is None, "a revoked key came back to life"
            assert await repo.authenticate(raw) is not None
        finally:
            await engine.close()
    finally:
        await _drop(pg, staging)
    print(
        f"[restore-drill] local measurement only: backup {backup_seconds:.1f}s, "
        f"restore+verify {restore_seconds:.1f}s, tables {before_backup}"
    )
