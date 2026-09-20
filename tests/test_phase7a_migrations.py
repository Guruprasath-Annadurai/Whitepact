# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Phase 7A 0050-0053 upgrade/downgrade and single Alembic head."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from responsibleai.db.engine import create_engine
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from tests.pg_test_url import isolated_pg_url

PHASE7A_TABLES = {
    "runtime_execution_requests",
    "governance_execution_authorizations",
    "runtime_execution_attempts",
    "runtime_worker_leases",
    "runtime_execution_fences",
    "runtime_execution_dispatch_outbox",
}


@pytest.fixture
async def pg_url() -> AsyncGenerator[str, None]:
    async for url in isolated_pg_url("wp_p7a_mig"):
        yield url


def test_single_head_0053() -> None:
    ini = _find_alembic_ini()
    assert ini is not None
    heads = ScriptDirectory.from_config(Config(str(ini))).get_heads()
    assert heads == ["0057"]


@pytest.mark.asyncio
async def test_upgrade_downgrade_0050_0053_when_empty(pg_url: str) -> None:
    ini = _find_alembic_ini()
    assert ini is not None
    env = _migration_env(pg_url)
    await _run_alembic(ini, env, "upgrade", "head")
    engine = create_engine(pg_url)
    try:
        async with engine.raw.connect() as conn:
            version = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            assert version == "0057"
            tables = set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
            assert PHASE7A_TABLES <= tables
            statuses = (
                await conn.execute(
                    text(
                        """
                        SELECT conname FROM pg_constraint
                        WHERE conname = 'chk_exec_auth_status'
                        """
                    )
                )
            ).fetchall()
            assert statuses
    finally:
        await engine.close()

    await _run_alembic(ini, env, "downgrade", "0049")
    engine = create_engine(pg_url)
    try:
        async with engine.raw.connect() as conn:
            version = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            assert version == "0049"
            tables = set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
            assert not (PHASE7A_TABLES & tables)
    finally:
        await engine.close()

    await _run_alembic(ini, env, "upgrade", "head")
    engine = create_engine(pg_url)
    try:
        async with engine.raw.connect() as conn:
            version = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            assert version == "0057"
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_requests_are_append_only(pg_url: str) -> None:
    ini = _find_alembic_ini()
    assert ini is not None
    env = _migration_env(pg_url)
    await _run_alembic(ini, env, "upgrade", "head")
    engine = create_engine(pg_url)
    try:
        async with engine.raw.begin() as conn:
            await conn.execute(
                text(
                    """
                    INSERT INTO organizations (id, name, slug, monthly_budget_usd, created_at)
                    VALUES ('org-immut', 'Immut', 'immut-p7a', 1000, '2026-01-01T00:00:00Z')
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    INSERT INTO runtime_execution_requests (
                        request_id, organization_id, principal_id, agent_id, identity_id,
                        intent, action_type, target, action_digest, canonical_action_payload,
                        approved_arguments, observed_governance_epoch, idempotency_key, lifecycle
                    ) VALUES (
                        'req-1', 'org-immut', 'p', 'a', 'i',
                        'intent', 'tool', 'tool', 'd' || repeat('0', 63), '{}',
                        '{}'::jsonb, 0, 'idemp-1', 'RECORDED'
                    )
                    """
                )
            )
        async with engine.raw.begin() as conn:
            with pytest.raises(Exception, match="immutable"):
                await conn.execute(
                    text(
                        "UPDATE runtime_execution_requests SET intent = 'mutated' WHERE request_id = 'req-1'"
                    )
                )
    finally:
        await engine.close()
