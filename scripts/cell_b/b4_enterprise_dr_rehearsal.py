#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""P1-A — Representative B4 disaster-recovery rehearsal (≥100k persisted rows)."""

from __future__ import annotations

import argparse
import asyncio
import gzip
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import asyncpg

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tests.pg_test_url import database_url, isolated_pg_url, resolve_admin_url

from responsibleai.db.audit_repository import AuditRepository, _compute_entry_hash
from responsibleai.db.engine import create_engine
from responsibleai.db.evidence_repository import EvidenceRepository
from responsibleai.db.migrate import run_migrations_or_raise
from responsibleai.rbac.models import AuditEntry

_CELL_B_DIR = Path(__file__).resolve().parent
if str(_CELL_B_DIR) not in sys.path:
    sys.path.insert(0, str(_CELL_B_DIR))
from b4_security_state import install_security_fixtures, verify_security_state

_GENESIS = "0" * 64
NOW = datetime.now(UTC).isoformat()


def _pg(url: str) -> dict[str, str]:
    p = urlparse(url)
    return {
        "host": p.hostname or "127.0.0.1",
        "port": str(p.port or 5432),
        "user": p.username or "wp",
        "password": p.password or "",
        "dbname": (p.path or "/postgres").lstrip("/"),
    }


async def _seed_enterprise_dataset(conn: asyncpg.Connection, targets: dict[str, int]) -> dict[str, int]:
    org_ids = [f"org-{uuid.uuid4().hex[:12]}" for _ in range(targets["organizations"])]
    org_rows = [
        (
            oid,
            f"Enterprise Org {i}",
            f"ent-org-{i}-{uuid.uuid4().hex[:6]}",
            10000.0,
            NOW,
        )
        for i, oid in enumerate(org_ids)
    ]
    await conn.executemany(
        """
        INSERT INTO organizations (id, name, slug, monthly_budget_usd, created_at)
        VALUES ($1, $2, $3, $4, $5)
        """,
        org_rows,
    )

    nonce_rows = []
    for i in range(targets["governance_execution_nonces"]):
        org_id = org_ids[i % len(org_ids)]
        nonce_rows.append(
            (
                hashlib.sha256(f"nonce-{i}".encode()).hexdigest(),
                f"auth-{uuid.uuid4().hex[:12]}",
                org_id,
                NOW,
            )
        )
    await conn.executemany(
        """
        INSERT INTO governance_execution_nonces
        (nonce, authorization_id, organization_id, consumed_at)
        VALUES ($1, $2, $3, $4)
        """,
        nonce_rows,
    )

    approval_rows = []
    for i in range(targets["governance_approvals"]):
        org_id = org_ids[i % len(org_ids)]
        status = "DENIED" if i % 17 == 0 else ("APPROVED" if i % 3 == 0 else "PENDING")
        approval_rows.append(
            (
                str(uuid.uuid4()),
                org_id,
                str(uuid.uuid4()),
                None,
                "EXECUTE",
                f"/resource/{i}",
                "[]",
                "MEDIUM",
                status,
                "seed-principal",
                NOW,
                "seed-resolver" if status != "PENDING" else None,
                NOW if status != "PENDING" else None,
                None,
            )
        )
    await conn.executemany(
        """
        INSERT INTO governance_approvals
        (id, org_id, action_id, evidence_id, action_type, target, reason_codes,
         risk_tier, status, requested_by, requested_at, resolved_by, resolved_at, resolution_notes)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
        """,
        approval_rows,
    )

    evidence_rows = []
    prev_hash = _GENESIS
    for i in range(targets["governance_evidence"]):
        org_id = org_ids[i % len(org_ids)]
        eid = str(uuid.uuid4())
        entry_hash = hashlib.sha256(
            f"{prev_hash}|{eid}|{org_id}|ALLOW|{NOW}".encode()
        ).hexdigest()
        evidence_rows.append(
            (
                eid,
                org_id,
                str(uuid.uuid4()),
                "agent-seed",
                "principal-seed",
                "EXECUTE",
                f"/target/{i}",
                "[]",
                "root",
                "LOW",
                "ALLOW",
                "[]",
                None,
                None,
                None,
                NOW,
                NOW,
                entry_hash,
                prev_hash,
            )
        )
        prev_hash = entry_hash
    await conn.executemany(
        """
        INSERT INTO governance_evidence
        (id, org_id, action_id, agent_id, identity_id, action_type, target,
         argument_keys, authority_delegated_by, risk_tier, decision, reason_codes,
         framework, provider, model, evaluated_at, recorded_at, entry_hash, prev_hash)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19)
        """,
        evidence_rows,
    )

    audit_rows = []
    prev = _GENESIS
    for i in range(targets["audit_log"]):
        org_id = org_ids[i % len(org_ids)]
        entry_id = str(uuid.uuid4())
        entry = AuditEntry(
            id=entry_id,
            timestamp=NOW,
            org_id=org_id,
            key_id="seed-key",
            endpoint=f"/api/seed/{i % 50}",
            method="GET",
            status_code=200,
        )
        entry_hash = _compute_entry_hash(prev, entry)
        audit_rows.append(
            (
                entry_id,
                NOW,
                org_id,
                "seed-key",
                entry.endpoint,
                "GET",
                200,
                None,
                f"req-{i}",
                1.0,
                None,
                entry_hash,
                prev,
            )
        )
        prev = entry_hash
    await conn.executemany(
        """
        INSERT INTO audit_log
        (id, timestamp, org_id, key_id, endpoint, method, status_code,
         ip_address, request_id, duration_ms, user_agent, entry_hash, prev_hash)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
        """,
        audit_rows,
    )

    counts = {}
    for table in targets:
        if table == "organizations":
            counts[table] = await conn.fetchval("SELECT COUNT(*) FROM organizations")
        elif table == "audit_log":
            counts[table] = await conn.fetchval("SELECT COUNT(*) FROM audit_log")
        elif table == "governance_execution_nonces":
            counts[table] = await conn.fetchval("SELECT COUNT(*) FROM governance_execution_nonces")
        elif table == "governance_approvals":
            counts[table] = await conn.fetchval("SELECT COUNT(*) FROM governance_approvals")
        elif table == "governance_evidence":
            counts[table] = await conn.fetchval("SELECT COUNT(*) FROM governance_evidence")
    counts["total_rows"] = sum(counts.values())
    return counts


async def _verify_post_restore(engine, restore_url: str, source_counts: dict[str, int]) -> dict:
    audit_repo = AuditRepository(engine)
    chain = await audit_repo.verify_chain(days=3650)
    conn = await asyncpg.connect(restore_url)
    try:
        restored_counts = {
            "organizations": await conn.fetchval("SELECT COUNT(*) FROM organizations"),
            "audit_log": await conn.fetchval("SELECT COUNT(*) FROM audit_log"),
            "governance_execution_nonces": await conn.fetchval(
                "SELECT COUNT(*) FROM governance_execution_nonces"
            ),
            "governance_approvals": await conn.fetchval("SELECT COUNT(*) FROM governance_approvals"),
            "governance_evidence": await conn.fetchval("SELECT COUNT(*) FROM governance_evidence"),
        }
        denied = await conn.fetchval(
            "SELECT COUNT(*) FROM governance_approvals WHERE status = 'DENIED'"
        )
        cross_tenant = await conn.fetchval(
            """
            SELECT COUNT(*) FROM governance_execution_nonces n
            JOIN organizations o ON o.id = n.organization_id
            WHERE o.slug IS NULL
            """
        )
        sample_org = await conn.fetchval("SELECT id FROM organizations LIMIT 1")
    finally:
        await conn.close()
    evidence_repo = EvidenceRepository(engine)
    evidence_ok = True
    if sample_org:
        records = await evidence_repo.list_for_org(sample_org, limit=5)
        evidence_ok = len(records) > 0

    return {
        "audit_chain": chain,
        "restored_counts": restored_counts,
        "counts_match_source": restored_counts == {
            k: source_counts[k] for k in restored_counts if k in source_counts
        },
        "denied_approvals_preserved": int(denied) == source_counts.get("denied_approvals", 0),
        "tenant_slug_referential_probe": cross_tenant == 0,
        "governance_evidence_readable": evidence_ok,
        "nonce_rows_preserved": restored_counts["governance_execution_nonces"]
        == source_counts["governance_execution_nonces"],
    }


async def run_rehearsal(output: Path, min_rows: int) -> int:
    targets = {
        "organizations": 100,
        "audit_log": 50_000,
        "governance_execution_nonces": 25_000,
        "governance_approvals": 15_000,
        "governance_evidence": 10_000,
    }
    if sum(targets.values()) < min_rows:
        raise RuntimeError("target row budget below minimum")

    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    admin = await resolve_admin_url()

    async for source_url in isolated_pg_url("b4_enterprise"):
        await run_migrations_or_raise(source_url)
        conn = await asyncpg.connect(source_url)
        try:
            t0 = time.monotonic()
            source_counts = await _seed_enterprise_dataset(conn, targets)
            seed_seconds = time.monotonic() - t0
            source_counts["denied_approvals"] = await conn.fetchval(
                "SELECT COUNT(*) FROM governance_approvals WHERE status = 'DENIED'"
            )
        finally:
            await conn.close()

        security_snapshot = await install_security_fixtures(source_url)
        conn = await asyncpg.connect(source_url)
        try:
            source_counts["organizations"] = await conn.fetchval(
                "SELECT COUNT(*) FROM organizations"
            )
            source_counts["governance_execution_nonces"] = await conn.fetchval(
                "SELECT COUNT(*) FROM governance_execution_nonces"
            )
            source_counts["governance_approvals"] = await conn.fetchval(
                "SELECT COUNT(*) FROM governance_approvals"
            )
            source_counts["denied_approvals"] = await conn.fetchval(
                "SELECT COUNT(*) FROM governance_approvals WHERE status = 'DENIED'"
            )
            source_counts["total_rows"] = (
                source_counts["organizations"]
                + source_counts["audit_log"]
                + source_counts["governance_execution_nonces"]
                + source_counts["governance_approvals"]
                + source_counts["governance_evidence"]
            )
        finally:
            await conn.close()

        src = _pg(source_url)
        env = {**os.environ, "PGPASSWORD": src["password"]}
        t_dump = time.monotonic()
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
        backup_plain = dump.stdout
        backup_gz = gzip.compress(backup_plain)
        backup_seconds = time.monotonic() - t_dump

        stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        restore_db = f"wp_b4_ent_rst_{stamp}"
        adm = _pg(admin)
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
        t_restore = time.monotonic()
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
            input=backup_plain.decode("utf-8"),
            text=True,
            env=env_a,
            capture_output=True,
        )
        restore_seconds = time.monotonic() - t_restore

        restore_url = database_url(admin, restore_db)
        engine = create_engine(restore_url)
        t_verify = time.monotonic()
        verification = await _verify_post_restore(engine, restore_url, source_counts)
        security_results = await verify_security_state(restore_url, security_snapshot)
        verify_seconds = time.monotonic() - t_verify

        security_out = output.parent / "b4-enterprise-dr-security-state.json"
        security_evidence = {
            "phase": "B4",
            "test": "enterprise_dr_security_state_restoration",
            "evidence_categories": ["RESTORE_TESTED", "REAL_POSTGRES_TESTED", "AUTHZ_VERIFIED"],
            "source_sha": sha,
            "timestamp": datetime.now(UTC).isoformat(),
            "security_snapshot": security_snapshot.to_dict(redact_secrets=True),
            "post_restore_verification": security_results,
            "limitations": (
                "Expired execution grant checked via executor validation path "
                "(_validate_authorization); durable Phase 7A kernel admission "
                "requires full runtime_execution_* graph — see "
                "tests/test_phase7a_authority_kernel.py."
            ),
        }
        security_out.write_text(json.dumps(security_evidence, indent=2) + "\n", encoding="utf-8")

        evidence = {
            "phase": "B4",
            "test": "enterprise_disaster_recovery_rehearsal",
            "evidence_categories": ["RESTORE_TESTED", "REAL_POSTGRES_TESTED"],
            "source_sha": sha,
            "timestamp": datetime.now(UTC).isoformat(),
            "environment": "disposable_postgresql_logical_backup",
            "dataset_targets": targets,
            "dataset_counts_after_seed": source_counts,
            "measured_seed_seconds": round(seed_seconds, 3),
            "backup_bytes_gzip": len(backup_gz),
            "backup_bytes_plain": len(backup_plain),
            "backup_sha256_gzip": hashlib.sha256(backup_gz).hexdigest(),
            "measured_backup_seconds": round(backup_seconds, 3),
            "measured_restore_seconds": round(restore_seconds, 3),
            "measured_verification_seconds": round(verify_seconds, 3),
            "verification": verification,
            "security_state_artifact": str(
                security_out.resolve().relative_to(REPO.resolve())
            ),
            "security_state_passed": security_results.get("passed"),
            "limitations": (
                "Synthetic enterprise dataset on disposable PostgreSQL; "
                "not a guaranteed enterprise RPO/RTO commitment."
            ),
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(evidence, indent=2))

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
        ok = (
            verification["counts_match_source"]
            and verification["audit_chain"]["intact"]
            and verification["nonce_rows_preserved"]
            and verification["tenant_slug_referential_probe"]
            and security_results.get("passed")
        )
        return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO / "artifacts" / "production" / "b4-enterprise-dr-rehearsal.json",
    )
    parser.add_argument("--min-rows", type=int, default=100_000)
    args = parser.parse_args()
    return asyncio.run(run_rehearsal(args.output, args.min_rows))


if __name__ == "__main__":
    raise SystemExit(main())
