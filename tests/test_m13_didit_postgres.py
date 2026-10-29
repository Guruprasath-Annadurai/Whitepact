"""Mandatory real-PostgreSQL concurrency proof; unavailable databases are errors."""

import asyncio

import pytest
from sqlalchemy import select

from responsibleai.db import create_engine
from responsibleai.db.engine import identity_provider_events
from tests.pg_test_url import isolated_pg_url
from tests.test_m13_didit_durability import apply, setup


@pytest.mark.asyncio
async def test_postgres_concurrent_duplicate_deliveries_commit_once(monkeypatch):
    async for url in isolated_pg_url("wp_didit_race"):
        db = create_engine(url)
        await db.init()
        try:
            service, body, user = await setup(db, monkeypatch)
            results = await asyncio.gather(*(apply(service, body) for _ in range(8)))
            assert sum(not r["duplicate"] for r in results) == 1
            async with db.raw.connect() as conn:
                records = (await conn.execute(select(identity_provider_events))).all()
            assert len(records) == 3
            assert (await service.get_human_status(user))["status"] == "IDENTITY_VERIFIED"
        finally:
            await db.close()
