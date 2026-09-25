#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Full PostgreSQL backup → destroy → restore with integrity manifest."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import text

from responsibleai.db.engine import create_engine
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from tests.pg_test_url import isolated_pg_url

TABLES = (
    "organizations",
    "web_users",
    "web_memberships",
    "org_api_keys",
    "governance_evidence",
    "governance_policies",
    "governance_approvals",
    "governance_execution_nonces",
    "audit_log",
)


async def _seed(conn) -> dict[str, Any]:
    await conn.execute(
        text("""
        INSERT INTO organizations (id, name, slug, monthly_budget_usd, plan, created_at)
        VALUES
          ('org_br_alpha', 'BR Alpha', 'br-alpha', 10000, 'ENTERPRISE', '2026-01-01T00:00:00Z'),
          ('org_br_beta', 'BR Beta', 'br-beta', 5000, 'PRO', '2026-01-02T00:00:00Z')
        ON CONFLICT DO NOTHING
    """)
    )
    await conn.execute(
        text("""
        INSERT INTO web_users (id, email, full_name, password_hash, disabled, created_at, updated_at)
        VALUES
          ('u_br_1', 'br1@example.com', 'BR One', 'hash', 0, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
        ON CONFLICT DO NOTHING
    """)
    )
    await conn.execute(
        text("""
        INSERT INTO web_memberships (id, user_id, org_id, role, created_at)
        VALUES ('m_br_1', 'u_br_1', 'org_br_alpha', 'admin', '2026-01-01T00:00:00Z')
        ON CONFLICT DO NOTHING
    """)
    )
    manifest: dict[str, Any] = {"orgs": ["org_br_alpha", "org_br_beta"], "users": ["u_br_1"]}
    counts: dict[str, int] = {}
    for table in TABLES:
        try:
            n = (await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))).scalar() or 0
            counts[table] = int(n)
        except Exception:
            counts[table] = -1
    manifest["table_counts"] = counts
    ver = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
    manifest["alembic_version"] = ver
    return manifest


async def _manifest(conn) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for table in TABLES:
        try:
            n = (await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))).scalar() or 0
            counts[table] = int(n)
        except Exception:
            counts[table] = -1
    ver = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
    return {"table_counts": counts, "alembic_version": ver}


def _pg_url_parts(url: str) -> dict[str, str]:
    # postgresql+asyncpg://user:pass@host:port/dbname
    u = url.replace("postgresql+asyncpg://", "").replace("postgresql://", "")
    auth, rest = u.split("@", 1)
    user, password = auth.split(":", 1)
    if "/" in rest:
        host_port, dbname = rest.split("/", 1)
    else:
        host_port, dbname = rest, "postgres"
    host, port = (host_port.split(":", 1) + ["5432"])[:2]
    return {"user": user, "password": password, "host": host, "port": port, "dbname": dbname}


async def main() -> int:
    async for db_url in isolated_pg_url("wp_phase0b_br"):
        ini = _find_alembic_ini()
        assert ini
        env = _migration_env(db_url)
        await _run_alembic(ini, env, "upgrade", "head")
        engine = create_engine(db_url)
        await engine.init(auto_create_tables=False)
        try:
            async with engine.raw.connect() as conn:
                pre = await _seed(conn)
                await conn.commit()
        finally:
            await engine.close()

        parts = _pg_url_parts(db_url)
        dump = Path(tempfile.gettempdir()) / "wp_phase0b_br.dump"
        envp = {**os.environ, "PGPASSWORD": parts["password"]}
        dump_cmd = [
            "pg_dump",
            "-h",
            parts["host"],
            "-p",
            parts["port"],
            "-U",
            parts["user"],
            "-Fc",
            "-f",
            str(dump),
            parts["dbname"],
        ]
        subprocess.check_call(dump_cmd, env=envp)

        admin = db_url.rsplit("/", 1)[0] + "/postgres"
        admin_parts = _pg_url_parts(admin)
        subprocess.check_call(
            [
                "psql",
                "-h",
                admin_parts["host"],
                "-p",
                admin_parts["port"],
                "-U",
                admin_parts["user"],
                "-d",
                "postgres",
                "-c",
                f"DROP DATABASE IF EXISTS {parts['dbname']} WITH (FORCE);",
            ],
            env={**os.environ, "PGPASSWORD": admin_parts["password"]},
        )
        subprocess.check_call(
            [
                "psql",
                "-h",
                admin_parts["host"],
                "-p",
                admin_parts["port"],
                "-U",
                admin_parts["user"],
                "-d",
                "postgres",
                "-c",
                f"CREATE DATABASE {parts['dbname']};",
            ],
            env={**os.environ, "PGPASSWORD": admin_parts["password"]},
        )
        subprocess.check_call(
            [
                "pg_restore",
                "-h",
                parts["host"],
                "-p",
                parts["port"],
                "-U",
                parts["user"],
                "-d",
                parts["dbname"],
                "--no-owner",
                str(dump),
            ],
            env=envp,
        )

        engine2 = create_engine(db_url)
        await engine2.init(auto_create_tables=False)
        try:
            async with engine2.raw.connect() as conn:
                post = await _manifest(conn)
        finally:
            await engine2.close()

        ok = pre["table_counts"] == post["table_counts"] and pre["alembic_version"] == post["alembic_version"]
        out = {
            "status": "PASS" if ok else "FAIL",
            "pre_manifest": pre,
            "post_manifest": post,
            "dump_bytes": dump.stat().st_size,
        }
        report = ROOT / "WHITEPACT_V131_95_FULL_BACKUP_RESTORE_REPORT.md"
        report.write_text(
            "# Full backup / restore (Phase 0B)\n\n"
            f"**Verdict:** **{out['status']}**\n\n"
            f"Dump size: {out['dump_bytes']} bytes\n\n"
            "## Pre manifest\n\n```json\n"
            + json.dumps(pre, indent=2)
            + "\n```\n\n## Post manifest\n\n```json\n"
            + json.dumps(post, indent=2)
            + "\n```\n",
            encoding="utf-8",
        )
        print(json.dumps(out, indent=2))
        return 0 if ok else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
