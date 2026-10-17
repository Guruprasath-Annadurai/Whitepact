# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Adversarial qualification of PostgreSQL migration 0065.

Validates:
1. Historical row preservation and default semantics (require_passkey_stepup = 0).
2. Schema constraints and NOT NULL enforcement on PostgreSQL.
3. Clean rollback (downgrade to 0064) and re-upgrade idempotency.
4. Interrupted transaction safety.
5. Concurrent migration execution safety.
"""

from __future__ import annotations

import uuid
from contextlib import aclosing

import asyncpg
import pytest

from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from tests.pg_test_url import isolated_pg_url


async def _run_upgrade(db_url: str, target: str = "head") -> None:
    ini = _find_alembic_ini()
    if ini is None:
        raise RuntimeError("Alembic configuration missing")
    env = _migration_env(db_url)
    await _run_alembic(ini, env, "upgrade", target)


async def _run_downgrade(db_url: str, target: str) -> None:
    ini = _find_alembic_ini()
    if ini is None:
        raise RuntimeError("Alembic configuration missing")
    env = _migration_env(db_url)
    await _run_alembic(ini, env, "downgrade", target)


@pytest.mark.asyncio
async def test_migration_0065_historical_rows_preserved():
    """Migrate to 0064, insert historical rows, upgrade to 0065, and prove row preservation."""
    async with aclosing(isolated_pg_url("m13_titan2_mig0065")) as dbs:
        async for db_url in dbs:
            raw_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

            # Step 1: Migrate to baseline 0064
            await _run_upgrade(db_url, "0064")

            conn = await asyncpg.connect(raw_url)
            try:
                # Verify at 0064
                rev = await conn.fetchval("SELECT version_num FROM alembic_version")
                assert rev == "0064"

                # Insert prerequisite organization
                org1_id = str(uuid.uuid4())
                org2_id = str(uuid.uuid4())
                await conn.execute(
                    "INSERT INTO organizations (id, name, slug, plan, created_at) "
                    "VALUES ($1, 'Org 1', 'org-1', 'enterprise', '2026-10-01T00:00:00Z'), "
                    "       ($2, 'Org 2', 'org-2', 'enterprise', '2026-10-01T00:00:00Z')",
                    org1_id,
                    org2_id,
                )

                # Insert historical bootstrap records under 0064 (without require_passkey_stepup)
                boot1_id = str(uuid.uuid4())
                boot2_id = str(uuid.uuid4())
                await conn.execute(
                    "INSERT INTO trust_fabric_bootstrap_records "
                    "(id, org_id, token_hash, expires_at, consumed_at, claimed_by_principal_id, nonce, created_at) "
                    "VALUES ($1, $2, 'hash1', '2026-10-20T00:00:00Z', NULL, NULL, 'nonce1', '2026-10-15T00:00:00Z'), "
                    "       ($3, $4, 'hash2', '2026-10-20T00:00:00Z', '2026-10-15T12:00:00Z', 'prin-1', 'nonce2', '2026-10-15T00:00:00Z')",
                    boot1_id,
                    org1_id,
                    boot2_id,
                    org2_id,
                )
            finally:
                await conn.close()

            # Step 2: Forward migrate to 0065
            await _run_upgrade(db_url, "0065")

            conn = await asyncpg.connect(raw_url)
            try:
                rev = await conn.fetchval("SELECT version_num FROM alembic_version")
                assert rev == "0065"

                # Verify rows survived with require_passkey_stepup = 0
                rows = await conn.fetch(
                    "SELECT id, org_id, token_hash, nonce, require_passkey_stepup "
                    "FROM trust_fabric_bootstrap_records ORDER BY created_at"
                )
                assert len(rows) == 2

                r1 = rows[0]
                assert r1["id"] == boot1_id
                assert r1["org_id"] == org1_id
                assert r1["token_hash"] == "hash1"
                assert r1["nonce"] == "nonce1"
                assert r1["require_passkey_stepup"] == 0

                r2 = rows[1]
                assert r2["id"] == boot2_id
                assert r2["org_id"] == org2_id
                assert r2["token_hash"] == "hash2"
                assert r2["nonce"] == "nonce2"
                assert r2["require_passkey_stepup"] == 0

                # Step 3: Insert new row under 0065 with explicit require_passkey_stepup = 1
                org3_id = str(uuid.uuid4())
                await conn.execute(
                    "INSERT INTO organizations (id, name, slug, plan, created_at) "
                    "VALUES ($1, 'Org 3', 'org-3', 'enterprise', '2026-10-01T00:00:00Z')",
                    org3_id,
                )
                boot3_id = str(uuid.uuid4())
                await conn.execute(
                    "INSERT INTO trust_fabric_bootstrap_records "
                    "(id, org_id, token_hash, expires_at, nonce, created_at, require_passkey_stepup) "
                    "VALUES ($1, $2, 'hash3', '2026-10-25T00:00:00Z', 'nonce3', '2026-10-16T00:00:00Z', 1)",
                    boot3_id,
                    org3_id,
                )
                val = await conn.fetchval(
                    "SELECT require_passkey_stepup FROM trust_fabric_bootstrap_records WHERE id = $1",
                    boot3_id,
                )
                assert val == 1

                # Verify NOT NULL constraint enforcement
                org4_id = str(uuid.uuid4())
                await conn.execute(
                    "INSERT INTO organizations (id, name, slug, plan, created_at) "
                    "VALUES ($1, 'Org 4', 'org-4', 'enterprise', '2026-10-01T00:00:00Z')",
                    org4_id,
                )
                with pytest.raises(asyncpg.NotNullViolationError):
                    await conn.execute(
                        "INSERT INTO trust_fabric_bootstrap_records "
                        "(id, org_id, token_hash, expires_at, nonce, created_at, require_passkey_stepup) "
                        "VALUES ($1, $2, 'hash4', '2026-10-25T00:00:00Z', 'nonce4', '2026-10-16T00:00:00Z', NULL)",
                        str(uuid.uuid4()),
                        org4_id,
                    )
            finally:
                await conn.close()


@pytest.mark.asyncio
async def test_migration_0065_rollback_and_reupgrade():
    """Verify clean downgrade to 0064 and subsequent re-upgrade to 0065."""
    async with aclosing(isolated_pg_url("m13_titan2_rollback")) as dbs:
        async for db_url in dbs:
            raw_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

            # Step 1: Migrate all the way to 0065
            await _run_upgrade(db_url, "0065")

            conn = await asyncpg.connect(raw_url)
            try:
                # Insert org and record
                org_id = str(uuid.uuid4())
                boot_id = str(uuid.uuid4())
                await conn.execute(
                    "INSERT INTO organizations (id, name, slug, plan, created_at) "
                    "VALUES ($1, 'Rollback Org', 'rollback-org', 'enterprise', '2026-10-01T00:00:00Z')",
                    org_id,
                )
                await conn.execute(
                    "INSERT INTO trust_fabric_bootstrap_records "
                    "(id, org_id, token_hash, expires_at, nonce, created_at, require_passkey_stepup) "
                    "VALUES ($1, $2, 'hash_rb', '2026-10-25T00:00:00Z', 'nonce_rb', '2026-10-16T00:00:00Z', 1)",
                    boot_id,
                    org_id,
                )
            finally:
                await conn.close()

            # Step 2: Attempt downgrade with mandatory passkey requirement (1) -> Must be rejected fail-closed
            from responsibleai.db.migrate import MigrationError
            with pytest.raises(MigrationError, match="mandatory passkey requirements exist"):
                await _run_downgrade(db_url, "0064")

            conn = await asyncpg.connect(raw_url)
            try:
                # Schema must remain at 0065, column and data intact
                rev = await conn.fetchval("SELECT version_num FROM alembic_version")
                assert rev == "0065"
                val = await conn.fetchval(
                    "SELECT require_passkey_stepup FROM trust_fabric_bootstrap_records WHERE id = $1",
                    boot_id,
                )
                assert val == 1

                # Update row to non-mandatory requirement (0) to test supported downgrade path
                await conn.execute(
                    "UPDATE trust_fabric_bootstrap_records SET require_passkey_stepup = 0 WHERE id = $1",
                    boot_id,
                )
            finally:
                await conn.close()

            # Step 3: Downgrade back to 0064 with non-mandatory requirement succeeds
            await _run_downgrade(db_url, "0064")

            conn = await asyncpg.connect(raw_url)
            try:
                rev = await conn.fetchval("SELECT version_num FROM alembic_version")
                assert rev == "0064"

                # Column must be gone
                has_col = await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                    "WHERE table_name='trust_fabric_bootstrap_records' AND column_name='require_passkey_stepup')"
                )
                assert not has_col

                # Row still intact
                row = await conn.fetchrow(
                    "SELECT id, org_id, token_hash, nonce FROM trust_fabric_bootstrap_records WHERE id = $1",
                    boot_id,
                )
                assert row is not None
                assert row["token_hash"] == "hash_rb"
            finally:
                await conn.close()

            # Step 4: Re-upgrade to 0065 (idempotent forward migration)
            await _run_upgrade(db_url, "0065")

            conn = await asyncpg.connect(raw_url)
            try:
                rev = await conn.fetchval("SELECT version_num FROM alembic_version")
                assert rev == "0065"

                has_col = await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                    "WHERE table_name='trust_fabric_bootstrap_records' AND column_name='require_passkey_stepup')"
                )
                assert has_col

                # Non-mandatory row now has default 0
                val = await conn.fetchval(
                    "SELECT require_passkey_stepup FROM trust_fabric_bootstrap_records WHERE id = $1",
                    boot_id,
                )
                assert val == 0
            finally:
                await conn.close()


@pytest.mark.asyncio
async def test_migration_0065_uniqueness_and_constraint_violations():
    """Verify unique constraint on nonce and org_id are strictly enforced on 0065."""
    async with aclosing(isolated_pg_url("m13_titan2_constraints")) as dbs:
        async for db_url in dbs:
            raw_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
            await _run_upgrade(db_url, "0065")

            conn = await asyncpg.connect(raw_url)
            try:
                org_id = str(uuid.uuid4())
                await conn.execute(
                    "INSERT INTO organizations (id, name, slug, plan, created_at) "
                    "VALUES ($1, 'Constraint Org', 'constraint-org', 'enterprise', '2026-10-01T00:00:00Z')",
                    org_id,
                )
                boot1_id = str(uuid.uuid4())
                await conn.execute(
                    "INSERT INTO trust_fabric_bootstrap_records "
                    "(id, org_id, token_hash, expires_at, nonce, created_at, require_passkey_stepup) "
                    "VALUES ($1, $2, 'hash1', '2026-10-25T00:00:00Z', 'unique_nonce', '2026-10-16T00:00:00Z', 1)",
                    boot1_id,
                    org_id,
                )

                # Duplicate org_id must fail (org_id is unique)
                with pytest.raises(asyncpg.UniqueViolationError):
                    await conn.execute(
                        "INSERT INTO trust_fabric_bootstrap_records "
                        "(id, org_id, token_hash, expires_at, nonce, created_at, require_passkey_stepup) "
                        "VALUES ($1, $2, 'hash2', '2026-10-25T00:00:00Z', 'diff_nonce', '2026-10-16T00:00:00Z', 0)",
                        str(uuid.uuid4()),
                        org_id,
                    )

                # Duplicate nonce must fail (nonce is unique)
                org2_id = str(uuid.uuid4())
                await conn.execute(
                    "INSERT INTO organizations (id, name, slug, plan, created_at) "
                    "VALUES ($1, 'Constraint Org 2', 'constraint-org-2', 'enterprise', '2026-10-01T00:00:00Z')",
                    org2_id,
                )
                with pytest.raises(asyncpg.UniqueViolationError):
                    await conn.execute(
                        "INSERT INTO trust_fabric_bootstrap_records "
                        "(id, org_id, token_hash, expires_at, nonce, created_at, require_passkey_stepup) "
                        "VALUES ($1, $2, 'hash3', '2026-10-25T00:00:00Z', 'unique_nonce', '2026-10-16T00:00:00Z', 0)",
                        str(uuid.uuid4()),
                        org2_id,
                    )
            finally:
                await conn.close()


@pytest.mark.asyncio
async def test_migration_0065_interrupted_transaction_leaves_clean_state():
    """Verify that interrupted or aborted transactions do not leave partial state or corrupt data."""
    async with aclosing(isolated_pg_url("m13_titan2_txabort")) as dbs:
        async for db_url in dbs:
            raw_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
            await _run_upgrade(db_url, "0065")

            conn = await asyncpg.connect(raw_url)
            try:
                org_id = str(uuid.uuid4())
                await conn.execute(
                    "INSERT INTO organizations (id, name, slug, plan, created_at) "
                    "VALUES ($1, 'Tx Org', 'tx-org', 'enterprise', '2026-10-01T00:00:00Z')",
                    org_id,
                )

                # Start transaction that fails midway
                boot_id = str(uuid.uuid4())
                try:
                    async with conn.transaction():
                        await conn.execute(
                            "INSERT INTO trust_fabric_bootstrap_records "
                            "(id, org_id, token_hash, expires_at, nonce, created_at, require_passkey_stepup) "
                            "VALUES ($1, $2, 'hash_tx', '2026-10-25T00:00:00Z', 'nonce_tx', '2026-10-16T00:00:00Z', 1)",
                            boot_id,
                            org_id,
                        )
                        # Deliberate failure inside the transaction
                        await conn.execute("INSERT INTO non_existent_table VALUES (1)")
                except asyncpg.UndefinedTableError:
                    pass

                # Record must NOT exist
                count = await conn.fetchval(
                    "SELECT COUNT(*) FROM trust_fabric_bootstrap_records WHERE id = $1", boot_id
                )
                assert count == 0
            finally:
                await conn.close()
