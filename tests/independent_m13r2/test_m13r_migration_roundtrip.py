# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Canonical migration on disposable PostgreSQL; no fixture-created tables."""

import asyncpg
import pytest

from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from tests.pg_test_url import isolated_pg_url

TABLES = {
    "authority_step_up_challenges",
    "authority_containment_records",
    "authority_recovery_requests",
    "authority_recovery_votes",
}


@pytest.mark.asyncio
async def test_0063_upgrade_0064_constraints_and_safe_empty_downgrade():
    async for url in isolated_pg_url("wp_m13r_roundtrip"):
        ini = _find_alembic_ini()
        assert ini is not None
        env = _migration_env(url)
        await _run_alembic(ini, env, "upgrade", "0063")
        await _run_alembic(ini, env, "upgrade", "head")
        conn = await asyncpg.connect(url)
        try:
            assert int(await conn.fetchval("SHOW server_version_num")) // 10000 == 16
            assert await conn.fetchval("SELECT version_num FROM alembic_version") == "0064"
            names = set(
                await conn.fetchval(
                    "SELECT array_agg(tablename) FROM pg_tables WHERE schemaname='public'"
                )
            )
            assert TABLES <= names
            constraints = await conn.fetch(
                "SELECT contype::text AS contype, pg_get_constraintdef(oid) AS definition FROM pg_constraint WHERE conrelid='authority_recovery_votes'::regclass"
            )
            assert any(
                row["contype"] == "u" and "request_id, voter_user_id" in row["definition"]
                for row in constraints
            )
            assert any(
                row["contype"] == "f" and "ON DELETE CASCADE" in row["definition"]
                for row in constraints
            )
            with pytest.raises(asyncpg.ForeignKeyViolationError):
                await conn.execute(
                    "INSERT INTO authority_recovery_votes (id,request_id,voter_user_id,decision,action_digest,voted_at) VALUES ('vote','missing','voter','APPROVE','digest','time')"
                )
            indexes = set(
                await conn.fetchval(
                    "SELECT array_agg(indexname) FROM pg_indexes WHERE schemaname='public'"
                )
            )
            assert {
                "idx_auth_stepup_user",
                "idx_auth_stepup_org",
                "idx_auth_stepup_digest",
                "idx_containment_org",
                "idx_containment_target",
                "idx_rec_req_org",
                "idx_rec_req_digest",
                "idx_rec_votes_req",
            } <= indexes
        finally:
            await conn.close()
        await _run_alembic(ini, env, "downgrade", "0063")
        conn = await asyncpg.connect(url)
        try:
            names = set(
                await conn.fetchval(
                    "SELECT array_agg(tablename) FROM pg_tables WHERE schemaname='public'"
                )
            )
            assert not TABLES & names
            assert await conn.fetchval("SELECT version_num FROM alembic_version") == "0063"
        finally:
            await conn.close()
        await _run_alembic(ini, env, "upgrade", "head")


@pytest.mark.asyncio
async def test_migration_accepts_runtime_generated_identifier_lengths():
    async for url in isolated_pg_url("wp_m13r_ids"):
        ini = _find_alembic_ini()
        assert ini is not None
        await _run_alembic(ini, _migration_env(url), "upgrade", "head")
        conn = await asyncpg.connect(url)
        try:
            # Exact current service prefixes plus uuid4().hex; no root authority seed.
            for table, prefix in [
                ("authority_containment_records", "wp_cnt_"),
                ("authority_recovery_requests", "wp_recov_"),
                ("authority_recovery_votes", "wp_rvote_"),
            ]:
                limit = await conn.fetchval(
                    "SELECT character_maximum_length FROM information_schema.columns WHERE table_schema='public' AND table_name=$1 AND column_name='id'",
                    table,
                )
                assert limit is None or limit >= len(prefix) + 32, (
                    f"{table}: runtime ID needs {len(prefix) + 32} characters, migrated column allows {limit}"
                )
        finally:
            await conn.close()
