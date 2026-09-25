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
import socket
import tempfile
import time
import urllib.request
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
    "governance_evidence_chain_heads",
    "governance_policies",
    "governance_approvals",
    "governance_execution_nonces",
    "governance_revocation_epochs",
    "audit_log",
    "paddle_webhook_events",
    "webhook_configs",
)


async def _seed(conn) -> dict[str, Any]:
    """Realistic multi-tenant state (aligned with historical migration preservation tests)."""
    await conn.execute(
        text("""
        INSERT INTO organizations (
            id, name, slug, monthly_budget_usd, plan, created_at,
            entitlement_version, entitlement_updated_at
        )
        VALUES
          ('tenant_alpha', 'Tenant Alpha Corp', 'tenant-alpha', 10000, 'ENTERPRISE',
           '2026-01-01T00:00:00Z', 3, '2026-01-01T12:00:00Z'),
          ('tenant_beta', 'Tenant Beta LLC', 'tenant-beta', 5000, 'PRO',
           '2026-01-02T00:00:00Z', 1, '2026-01-02T12:00:00Z')
        ON CONFLICT DO NOTHING
    """)
    )
    await conn.execute(
        text("""
        INSERT INTO web_users (id, email, full_name, password_hash, disabled, created_at, updated_at)
        VALUES
          ('usr_alpha_admin', 'admin@alpha.com', 'Alpha Admin', 'hash_adm', 0,
           '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z'),
          ('usr_alpha_viewer', 'viewer@alpha.com', 'Alpha Viewer', 'hash_view', 0,
           '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z'),
          ('usr_beta_member', 'member@beta.com', 'Beta Member', 'hash_mem', 0,
           '2026-01-02T00:00:00Z', '2026-01-02T00:00:00Z')
        ON CONFLICT DO NOTHING
    """)
    )
    await conn.execute(
        text("""
        INSERT INTO web_memberships (id, user_id, org_id, role, created_at)
        VALUES
          ('mem_alpha_adm', 'usr_alpha_admin', 'tenant_alpha', 'admin', '2026-01-01T00:00:00Z'),
          ('mem_alpha_viw', 'usr_alpha_viewer', 'tenant_alpha', 'viewer', '2026-01-01T00:00:00Z'),
          ('mem_beta_mem', 'usr_beta_member', 'tenant_beta', 'member', '2026-01-02T00:00:00Z')
        ON CONFLICT DO NOTHING
    """)
    )
    await conn.execute(
        text("""
        INSERT INTO org_api_keys (id, org_id, key_hash, name, role, created_at, revoked)
        VALUES
          ('key_alpha_act', 'tenant_alpha', 'hash_k1', 'Active Key', 'ADMIN', '2026-01-01T00:00:00Z', 0),
          ('key_alpha_rev', 'tenant_alpha', 'hash_k2', 'Revoked Key', 'ANALYST', '2026-01-01T00:00:00Z', 1),
          ('key_beta_act', 'tenant_beta', 'hash_k3', 'Beta Active', 'OPERATOR', '2026-01-02T00:00:00Z', 0)
        ON CONFLICT DO NOTHING
    """)
    )
    await conn.execute(
        text("""
        INSERT INTO governance_policies (id, org_id, rule_id, reason_code, effect, position, created_at, updated_at)
        VALUES
          ('pol_alpha_deny', 'tenant_alpha', 'rule_alpha_deny', 'BLOCKED_BY_POLICY', 'DENY', 1,
           '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z'),
          ('pol_beta_allow', 'tenant_beta', 'rule_beta_allow', 'STANDARD_ALLOW', 'ALLOW', 1,
           '2026-01-02T00:00:00Z', '2026-01-02T00:00:00Z')
        ON CONFLICT DO NOTHING
    """)
    )
    await conn.execute(
        text("""
        INSERT INTO governance_evidence (
            id, org_id, action_id, agent_id, identity_id, action_type, target,
            authority_delegated_by, decision, reason_codes, evaluated_at, recorded_at,
            entry_hash, prev_hash, integrity_version, integrity_status, chain_sequence
        )
        VALUES
          ('ev_alpha_1', 'tenant_alpha', 'act_a1', 'agt_a', 'id_a', 'tool_call', 'fs', 'root', 'DENY',
           '["POLICY_DENY"]', '2026-01-01T10:00:00Z', '2026-01-01T10:00:00Z',
           'hash_e1', NULL, 1, 'LEGACY_CHAINED_V1', 1),
          ('ev_alpha_2', 'tenant_alpha', 'act_a2', 'agt_a', 'id_a', 'tool_call', 'fs', 'root', 'ALLOW',
           '["PERMITTED"]', '2026-01-01T11:00:00Z', '2026-01-01T11:00:00Z',
           'hash_e2', 'hash_e1', 1, 'LEGACY_CHAINED_V1', 2),
          ('ev_beta_1', 'tenant_beta', 'act_b1', 'agt_b', 'id_b', 'tool_call', 'fs', 'root', 'DENY',
           '["POLICY_DENY"]', '2026-01-02T10:00:00Z', '2026-01-02T10:00:00Z',
           'hash_e3', NULL, 1, 'LEGACY_CHAINED_V1', 1)
        ON CONFLICT DO NOTHING
    """)
    )
    await conn.execute(
        text("""
        INSERT INTO governance_evidence_chain_heads (org_id, head_hash, sequence, updated_at)
        VALUES
          ('tenant_alpha', 'hash_head_alpha', 2, '2026-01-01T11:00:00Z'),
          ('tenant_beta', 'hash_head_beta', 1, '2026-01-02T10:00:00Z')
        ON CONFLICT DO NOTHING
    """)
    )
    await conn.execute(
        text("""
        INSERT INTO governance_revocation_epochs (organization_id, scope, epoch, updated_at)
        VALUES
          ('tenant_alpha', 'global', 42, '2026-01-01T12:00:00Z'),
          ('tenant_beta', 'global', 17, '2026-01-02T12:00:00Z')
        ON CONFLICT DO NOTHING
    """)
    )
    await conn.execute(
        text("""
        INSERT INTO governance_execution_nonces (nonce, authorization_id, organization_id, consumed_at)
        VALUES ('nonce_alpha_1', 'auth_a1', 'tenant_alpha', '2026-01-01T10:00:00Z')
        ON CONFLICT DO NOTHING
    """)
    )
    await conn.execute(
        text("""
        INSERT INTO governance_approvals (
            id, org_id, action_id, action_type, target, reason_codes, risk_tier, status,
            requested_by, requested_at, action_digest, expires_at, resolved_by, resolved_at
        )
        VALUES
          ('app_alpha_pnd', 'tenant_alpha', 'act_ap1', 'elevated_action', 'res1', '["HIGH_RISK"]',
           'HIGH', 'PENDING', 'usr_alpha_admin', '2026-01-01T12:00:00Z', 'dig_a1', '2026-01-01T13:00:00Z',
           NULL, NULL),
          ('app_beta_done', 'tenant_beta', 'act_bp2', 'export', 'res2', '["STANDARD"]',
           'MEDIUM', 'APPROVED', 'usr_beta_member', '2026-01-02T12:00:00Z', 'dig_b2', '2026-01-02T13:00:00Z',
           'usr_beta_member', '2026-01-02T12:30:00Z'),
          ('app_beta_rej', 'tenant_beta', 'act_bp1', 'export', 'res2', '["UNAUTHORIZED"]',
           'CRITICAL', 'REJECTED', 'usr_beta_member', '2026-01-02T12:00:00Z', 'dig_b1', '2026-01-02T13:00:00Z',
           'usr_beta_member', '2026-01-02T12:05:00Z')
        ON CONFLICT DO NOTHING
    """)
    )
    await conn.execute(
        text("""
        INSERT INTO audit_log (
            id, timestamp, org_id, key_id, endpoint, method, status_code, request_id, entry_hash, prev_hash
        )
        VALUES
          ('aud_a1', '2026-01-01T10:00:00Z', 'tenant_alpha', 'key_alpha_act', '/api/v1/governance/check', 'POST',
           200, 'req-a1', 'aud_hash_1', NULL),
          ('aud_b1', '2026-01-02T10:00:00Z', 'tenant_beta', 'key_beta_act', '/api/health', 'GET',
           200, 'req-b1', 'aud_hash_2', NULL)
        ON CONFLICT DO NOTHING
    """)
    )
    await conn.execute(
        text("""
        INSERT INTO paddle_webhook_events (
            event_id, event_type, occurred_at, entity_id, org_id, payload_hash, status, received_at
        )
        VALUES
          ('evt_paddle_1', 'subscription.updated', '2026-01-01T09:00:00Z', 'sub_1', 'tenant_alpha',
           'phash1', 'processed', '2026-01-01T09:00:01Z')
        ON CONFLICT DO NOTHING
    """)
    )
    await conn.execute(
        text("""
        INSERT INTO webhook_configs (id, org_id, url, provider, events, enabled, max_retries, created_at)
        VALUES
          ('wh_cfg_a', 'tenant_alpha', 'https://hooks.example.com/a', 'generic', '["approval_requested"]',
           1, 3, '2026-01-01T08:00:00Z')
        ON CONFLICT DO NOTHING
    """)
    )

    manifest: dict[str, Any] = {
        "orgs": ["tenant_alpha", "tenant_beta"],
        "users": ["usr_alpha_admin", "usr_alpha_viewer", "usr_beta_member"],
        "api_keys": {"active": ["key_alpha_act", "key_beta_act"], "revoked": ["key_alpha_rev"]},
        "evidence_ids": ["ev_alpha_1", "ev_alpha_2", "ev_beta_1"],
        "chain_heads": {"tenant_alpha": "hash_head_alpha", "tenant_beta": "hash_head_beta"},
        "approvals": {"pending": ["app_alpha_pnd"], "approved": ["app_beta_done"], "rejected": ["app_beta_rej"]},
        "nonces": ["nonce_alpha_1"],
        "paddle_events": ["evt_paddle_1"],
    }
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
    revoked = (
        await conn.execute(
            text("SELECT id FROM org_api_keys WHERE revoked = 1 ORDER BY id")
        )
    ).scalars().all()
    head_alpha = (
        await conn.execute(
            text(
                "SELECT head_hash FROM governance_evidence_chain_heads WHERE org_id = 'tenant_alpha'"
            )
        )
    ).scalar()
    return {
        "table_counts": counts,
        "alembic_version": ver,
        "revoked_keys": list(revoked),
        "alpha_chain_head": head_alpha,
    }


def _pg_url_parts(url: str) -> dict[str, str]:
    u = url.replace("postgresql+asyncpg://", "").replace("postgresql://", "")
    auth, rest = u.split("@", 1)
    user, password = auth.split(":", 1)
    if "/" in rest:
        host_port, dbname = rest.split("/", 1)
    else:
        host_port, dbname = rest, "postgres"
    host, port = (host_port.split(":", 1) + ["5432"])[:2]
    return {"user": user, "password": password, "host": host, "port": port, "dbname": dbname}


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _boot_health_check(db_url: str, port: int | None = None) -> dict[str, Any]:
    """Start WhitePact briefly against restored PostgreSQL and probe /api/health."""
    port = port or _free_port()
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    env = {
        **os.environ,
        "RAI_DATABASE_URL": sync_url,
        "WHITEPACT_ENV": "development",
        "WHITEPACT_LOG_LEVEL": "ERROR",
        "PYTHONPATH": f"{ROOT / 'src'}:{ROOT}",
    }
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "responsibleai.dashboard.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--workers",
            "1",
            "--no-access-log",
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    result: dict[str, Any] = {"port": port, "pid": proc.pid}
    try:
        for _ in range(120):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as resp:
                    result["health_status"] = resp.status
                    result["health_body"] = resp.read(500).decode("utf-8", errors="replace")
                    break
            except Exception:
                time.sleep(0.25)
        else:
            result["health_status"] = None
            result["error"] = "timeout_waiting_for_health"
            if proc.poll() is not None:
                err = proc.stderr.read(8000) if proc.stderr else b""
                result["stderr"] = err.decode("utf-8", errors="replace")[-4000:]
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
    result["ok"] = result.get("health_status") == 200
    return result


async def main() -> int:
    boot_port = int(os.environ["WHITEPACT_0B_BOOT_PORT"]) if os.environ.get("WHITEPACT_0B_BOOT_PORT") else None
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
                cross = (
                    await conn.execute(
                        text(
                            "SELECT COUNT(*) FROM org_api_keys WHERE org_id = 'tenant_beta' AND id = 'key_alpha_act'"
                        )
                    )
                ).scalar()
                post["cross_tenant_key_leak"] = int(cross or 0)
        finally:
            await engine2.close()

        boot = _boot_health_check(db_url, boot_port)
        ok_counts = pre["table_counts"] == post["table_counts"]
        ok_ver = pre["alembic_version"] == post["alembic_version"]
        ok_integrity = post.get("revoked_keys") == ["key_alpha_rev"] and post.get("alpha_chain_head") == "hash_head_alpha"
        ok_tenant = post.get("cross_tenant_key_leak", 1) == 0
        ok = ok_counts and ok_ver and ok_integrity and ok_tenant and boot.get("ok")
        out = {
            "status": "PASS" if ok else "FAIL",
            "pre_manifest": pre,
            "post_manifest": post,
            "dump_bytes": dump.stat().st_size,
            "post_restore_boot": boot,
            "checks": {
                "table_counts": ok_counts,
                "alembic": ok_ver,
                "integrity_sample": ok_integrity,
                "tenant_isolation": ok_tenant,
                "app_boot": boot.get("ok"),
            },
        }
        depth = "PASS" if pre["table_counts"].get("governance_evidence", 0) >= 3 else "PARTIAL"
        report = ROOT / "WHITEPACT_V131_95_FULL_BACKUP_RESTORE_REPORT.md"
        report.write_text(
            "# Full backup / restore (Phase 0B)\n\n"
            f"**Verdict:** **{out['status']}** (destroy + restore + manifest match)\n\n"
            f"**Population depth:** **{depth}** (multi-org users, keys, policies, evidence chain, "
            "approvals, nonces, audit, paddle webhook, webhook config)\n\n"
            f"Dump size: {out['dump_bytes']} bytes\n\n"
            "## Checks\n\n```json\n"
            + json.dumps(out["checks"], indent=2)
            + "\n```\n\n## Post-restore app boot\n\n```json\n"
            + json.dumps(boot, indent=2)
            + "\n```\n\n## Pre manifest\n\n```json\n"
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
