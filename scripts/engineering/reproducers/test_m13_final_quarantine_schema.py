# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real PostgreSQL schema/denial proof, not a customer grant or disposition."""

from contextlib import aclosing

import pytest
from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError
from tests.pg_test_url import isolated_pg_url

from responsibleai.db.engine import create_engine, organizations
from responsibleai.db.execution_nonce_repository import (
    ExecutionNonceRepository,
    OrganizationNotGovernableError,
)
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic


@pytest.mark.asyncio
async def test_actual_postgres_requires_disabled_and_execution_remains_denied():
    async with aclosing(isolated_pg_url("wp_final_schema")) as databases:
        async for database in databases:
            await _run_alembic(_find_alembic_ini(), _migration_env(database), "upgrade", "head")
            engine = create_engine(database)
            try:
                async with engine.raw.begin() as conn:
                    await conn.execute(
                        insert(organizations).values(
                            id="schema-proof",
                            name="Schema proof",
                            slug="schema-proof",
                            created_at="2026-10-19T12:00:00Z",
                            governance_status="ACTIVE",
                        )
                    )
                with pytest.raises(IntegrityError, match="chk_org_governance_status"):
                    async with engine.raw.begin() as conn:
                        await conn.execute(
                            update(organizations)
                            .where(
                                organizations.c.id == "schema-proof",
                            )
                            .values(governance_status="QUARANTINED")
                        )
                async with engine.raw.begin() as conn:
                    assert (
                        await conn.scalar(
                            select(organizations.c.governance_status).where(
                                organizations.c.id == "schema-proof",
                            )
                        )
                        == "ACTIVE"
                    )
                    await conn.execute(
                        update(organizations)
                        .where(
                            organizations.c.id == "schema-proof",
                        )
                        .values(governance_status="DISABLED")
                    )
                with pytest.raises(OrganizationNotGovernableError):
                    await ExecutionNonceRepository(engine).consume(
                        "negative-only",
                        authorization_id="not-a-grant",
                        organization_id="schema-proof",
                        expected_epoch=0,
                    )
            finally:
                await engine.close()
