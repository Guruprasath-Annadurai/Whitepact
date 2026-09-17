# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""PostgreSQL concurrency proofs for current V1 authority guarantees.

Skipped when local PostgreSQL (asyncpg at postgresql://ag@localhost/postgres?host=/tmp)
is unavailable — the suite must not fail closed into a false green on SQLite.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator

import pytest

from responsibleai.db import OrgRepository, create_engine
from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository
from responsibleai.rbac.models import GovernanceStatus, Plan

PG_ADMIN_URL = "postgresql://ag@localhost/postgres?host=/tmp"
PG_BASE_URL = "postgresql://ag@localhost/{db_name}?host=/tmp"


async def _postgres_reachable() -> bool:
    try:
        import asyncpg
    except ImportError:
        return False
    try:
        conn = await asyncpg.connect(PG_ADMIN_URL, timeout=2)
        await conn.close()
        return True
    except Exception:
        return False


@pytest.fixture
async def pg_url() -> AsyncGenerator[str, None]:
    if not await _postgres_reachable():
        pytest.skip("PostgreSQL test instance not available")
    import asyncpg
    db_name = f"wp_v1_hard_{uuid.uuid4().hex[:12]}"
    admin = await asyncpg.connect(PG_ADMIN_URL)
    await admin.execute(f'CREATE DATABASE "{db_name}"')
    await admin.close()
    url = PG_BASE_URL.format(db_name=db_name)
    engine = create_engine(url)
    try:
        await engine.init()
    except Exception:
        await engine.close()
        pytest.skip("PostgreSQL test database could not be initialized")
    await engine.close()
    try:
        yield url
    finally:
        admin = await asyncpg.connect(PG_ADMIN_URL)
        await admin.execute(
            f"""
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = '{db_name}' AND pid <> pg_backend_pid()
            """
        )
        await admin.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
        await admin.close()


@pytest.mark.asyncio
async def test_postgres_governance_status_epoch_is_serialized(pg_url: str) -> None:
    """Two connections racing set_governance_status produce monotonic epochs."""
    engine_a = create_engine(pg_url)
    engine_b = create_engine(pg_url)
    await engine_a.init()
    await engine_b.init()
    try:
        org_a = OrgRepository(engine_a)
        org = await org_a.create_org("PG Gov", f"pg-gov-{uuid.uuid4().hex[:8]}", plan=Plan.ENTERPRISE)
        org_b = OrgRepository(engine_b)
        epochs = RevocationEpochRepository(engine_a)

        async def suspend() -> None:
            await org_a.set_governance_status(org.id, GovernanceStatus.SUSPENDED)

        async def disable() -> None:
            await org_b.set_governance_status(org.id, GovernanceStatus.DISABLED)

        await asyncio.gather(suspend(), disable())
        current = await epochs.current(org.id)
        assert current.epoch >= 2
        loaded = await org_a.get_org(org.id)
        assert loaded is not None
        assert loaded.governance_status in {
            GovernanceStatus.SUSPENDED.value,
            GovernanceStatus.DISABLED.value,
        }
    finally:
        await engine_a.close()
        await engine_b.close()
