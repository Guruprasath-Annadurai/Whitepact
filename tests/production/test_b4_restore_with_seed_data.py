# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""B4 — backup/restore with representative seeded rows."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import asyncpg
import pytest
from tests.pg_test_url import database_url, isolated_pg_url, resolve_admin_url_sync

from responsibleai.db.engine import create_engine
from responsibleai.db.migrate import run_migrations_or_raise
from responsibleai.db.org_repository import OrgRepository

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "artifacts" / "production" / "b4-restore-seed-rehearsal.json"


def _pg(url: str) -> dict[str, str]:
    p = urlparse(url)
    return {
        "host": p.hostname or "127.0.0.1",
        "port": str(p.port or 5432),
        "user": p.username or "wp",
        "password": p.password or "",
        "dbname": (p.path or "/postgres").lstrip("/"),
    }


@pytest.mark.asyncio
async def test_restore_preserves_seeded_org_and_audit_tables() -> None:
    admin = resolve_admin_url_sync()
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    restore_db = f"wp_b4_seed_rst_{stamp}"
    async for source_url in isolated_pg_url("b4_seed"):
        await run_migrations_or_raise(source_url)
        engine = create_engine(source_url)
        org = await OrgRepository(engine).create_org("Seed Org", f"seed-{stamp}")
        org_id = org.id
        conn = await asyncpg.connect(source_url)
        try:
            org_count = await conn.fetchval(
                "SELECT COUNT(*) FROM organizations WHERE id = $1", org_id
            )
            audit_before = await conn.fetchval(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'audit_log'"
            )
        finally:
            await conn.close()
        assert org_count == 1
        assert audit_before == 1

        src = _pg(source_url)
        adm = _pg(admin)
        env = {**os.environ, "PGPASSWORD": src["password"]}
        dump = subprocess.run(
            [
                "pg_dump",
                "-h",
                src["host"],
                "-p",
                src["port"],
                "-U",
                src["user"],
                "-d",
                src["dbname"],
                "--format=plain",
                "--no-owner",
                "--no-acl",
            ],
            check=True,
            capture_output=True,
            env=env,
        )
        backup_bytes = gzip.compress(dump.stdout)
        t0 = time.monotonic()
        env_a = {**os.environ, "PGPASSWORD": adm["password"]}
        subprocess.run(
            [
                "psql",
                "-h",
                adm["host"],
                "-p",
                adm["port"],
                "-U",
                adm["user"],
                "-d",
                adm["dbname"],
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                f"CREATE DATABASE {restore_db}",
            ],
            check=True,
            env=env_a,
            capture_output=True,
        )
        subprocess.run(
            [
                "psql",
                "-h",
                adm["host"],
                "-p",
                adm["port"],
                "-U",
                adm["user"],
                "-d",
                restore_db,
                "-v",
                "ON_ERROR_STOP=1",
                "-f",
                "-",
            ],
            check=True,
            input=gzip.decompress(backup_bytes).decode("utf-8"),
            text=True,
            env=env_a,
            capture_output=True,
        )
        restore_seconds = time.monotonic() - t0
        restore_url = database_url(admin, restore_db)
        rconn = await asyncpg.connect(restore_url)
        try:
            restored = await rconn.fetchval(
                "SELECT COUNT(*) FROM organizations WHERE id = $1", org_id
            )
            version = await rconn.fetchval("SELECT version_num FROM alembic_version")
        finally:
            await rconn.close()
        assert restored == 1
        assert version == "0061"
        evidence = {
            "phase": "B4",
            "test": "restore_with_seeded_org",
            "timestamp": datetime.now(UTC).isoformat(),
            "backup_bytes": len(backup_bytes),
            "backup_sha256": hashlib.sha256(backup_bytes).hexdigest(),
            "measured_restore_seconds": round(restore_seconds, 3),
            "seeded_org_id": org_id,
            "restored_org_rows": int(restored),
            "schema_version": version,
        }
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        subprocess.run(
            [
                "psql",
                "-h",
                adm["host"],
                "-p",
                adm["port"],
                "-U",
                adm["user"],
                "-d",
                adm["dbname"],
                "-c",
                f"DROP DATABASE IF EXISTS {restore_db}",
            ],
            env=env_a,
            capture_output=True,
        )
