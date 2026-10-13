# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""Launch Cell B — PostgreSQL backup/restore rehearsal (B4)."""

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

from responsibleai.db.migrate import run_migrations_or_raise

REPO = Path(__file__).resolve().parents[2]
EVIDENCE_DIR = REPO / "artifacts" / "production"


def _parse_pg_url(url: str) -> dict[str, str]:
    parsed = urlparse(url)
    return {
        "host": parsed.hostname or "127.0.0.1",
        "port": str(parsed.port or 5432),
        "user": parsed.username or "wp",
        "password": parsed.password or "",
        "dbname": (parsed.path or "/postgres").lstrip("/"),
    }


@pytest.mark.asyncio
async def test_logical_backup_restore_rehearsal_records_evidence() -> None:
    """REAL_POSTGRES_TESTED + RESTORE_TESTED on disposable isolated PostgreSQL."""
    admin = resolve_admin_url_sync()
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    restore_db = f"wp_b4_rst_{stamp}"

    async for source_url in isolated_pg_url("b4_src"):
        await run_migrations_or_raise(source_url)
        conn = await asyncpg.connect(source_url)
        try:
            table_count = await conn.fetchval(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
            )
            org_count = await conn.fetchval("SELECT COUNT(*) FROM organizations")
        finally:
            await conn.close()

        src_pg = _parse_pg_url(source_url)
        admin_pg = _parse_pg_url(admin)
        env = {**os.environ, "PGPASSWORD": src_pg["password"]}
        backup_path = Path(f"/tmp/wp-b4-backup-{stamp}.sql.gz")
        backup_start = time.monotonic()
        dump = subprocess.run(
            [
                "pg_dump",
                "-h",
                src_pg["host"],
                "-p",
                src_pg["port"],
                "-U",
                src_pg["user"],
                "-d",
                src_pg["dbname"],
                "--format=plain",
                "--no-owner",
                "--no-acl",
            ],
            check=True,
            capture_output=True,
            env=env,
        )
        backup_path.write_bytes(gzip.compress(dump.stdout))
        backup_seconds = time.monotonic() - backup_start
        checksum = hashlib.sha256(backup_path.read_bytes()).hexdigest()

        env_admin = {**os.environ, "PGPASSWORD": admin_pg["password"]}
        subprocess.run(
            [
                "psql",
                "-h",
                admin_pg["host"],
                "-p",
                admin_pg["port"],
                "-U",
                admin_pg["user"],
                "-d",
                admin_pg["dbname"],
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                f"CREATE DATABASE {restore_db}",
            ],
            check=True,
            env=env_admin,
            capture_output=True,
        )
        restore_url = database_url(admin, restore_db)
        restore_start = time.monotonic()
        sql = gzip.decompress(backup_path.read_bytes()).decode("utf-8")
        subprocess.run(
            [
                "psql",
                "-h",
                admin_pg["host"],
                "-p",
                admin_pg["port"],
                "-U",
                admin_pg["user"],
                "-d",
                restore_db,
                "-v",
                "ON_ERROR_STOP=1",
                "-f",
                "-",
            ],
            check=True,
            input=sql,
            text=True,
            env=env_admin,
            capture_output=True,
        )
        restore_seconds = time.monotonic() - restore_start

        rconn = await asyncpg.connect(restore_url)
        try:
            restored_tables = await rconn.fetchval(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
            )
            restored_orgs = await rconn.fetchval("SELECT COUNT(*) FROM organizations")
            version = await rconn.fetchval("SELECT version_num FROM alembic_version")
        finally:
            await rconn.close()

        assert restored_tables == table_count
        assert restored_orgs == org_count
        assert version

        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        evidence = {
            "phase": "B4",
            "test": "logical_backup_restore_rehearsal",
            "timestamp": datetime.now(UTC).isoformat(),
            "evidence_categories": ["REAL_POSTGRES_TESTED", "RESTORE_TESTED"],
            "postgres_version": subprocess.check_output(
                [
                    "psql",
                    "-h",
                    admin_pg["host"],
                    "-p",
                    admin_pg["port"],
                    "-U",
                    admin_pg["user"],
                    "-d",
                    admin_pg["dbname"],
                    "-tAc",
                    "SHOW server_version",
                ],
                env=env_admin,
                text=True,
            ).strip(),
            "backup_command": "pg_dump --format=plain | gzip",
            "measured_backup_seconds": round(backup_seconds, 3),
            "measured_restore_seconds": round(restore_seconds, 3),
            "backup_bytes": backup_path.stat().st_size,
            "backup_sha256": checksum,
            "schema_version": version,
            "source_row_counts": {
                "public_tables": int(table_count),
                "organizations": int(org_count),
            },
            "restored_row_counts": {
                "public_tables": int(restored_tables),
                "organizations": int(restored_orgs),
            },
            "limitations": "Disposable isolated PostgreSQL; not production data or RTO guarantee.",
        }
        out = EVIDENCE_DIR / "b4-restore-rehearsal.json"
        out.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")

        subprocess.run(
            [
                "psql",
                "-h",
                admin_pg["host"],
                "-p",
                admin_pg["port"],
                "-U",
                admin_pg["user"],
                "-d",
                admin_pg["dbname"],
                "-c",
                f"DROP DATABASE IF EXISTS {restore_db}",
            ],
            check=False,
            env=env_admin,
            capture_output=True,
        )
        backup_path.unlink(missing_ok=True)
