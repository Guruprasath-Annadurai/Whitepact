# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Independent PostgreSQL contract checks; Cursor owns the implementation.

All index faults are confined to disposable databases. A matching index name
is not proof that provider/session uniqueness is actually enforced.
"""

from contextlib import aclosing
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import insert, text

from responsibleai.db.engine import create_engine, identity_verifications
from responsibleai.db.identity_session_uniqueness import IDENTITY_SESSION_INDEX
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from responsibleai.db.runtime_compatibility import assert_runtime_schema_compatible
from responsibleai.db.web_identity_repository import WebIdentityRepository
from tests.pg_test_url import isolated_pg_url


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["non_unique", "wrong_columns", "partial"])
async def test_named_but_ineffective_session_index_cannot_qualify_startup(fault):
    async with aclosing(isolated_pg_url("codex_index_contract")) as databases:
        async for url in databases:
            await _run_alembic(_find_alembic_ini(), _migration_env(url), "upgrade", "head")
            engine = create_engine(url)
            try:
                web = WebIdentityRepository(engine)
                users = []
                for suffix in ("a", "b"):
                    user, _ = await web.register(
                        "Disposable index subject",
                        f"index-{suffix}@example.test",
                        "Isolated-Contract-Only-42!",
                    )
                    users.append(user)
                async with engine.raw.begin() as connection:
                    assert (
                        await connection.scalar(text("SELECT version_num FROM alembic_version"))
                        == "0067"
                    )
                    await connection.execute(text(f"DROP INDEX {IDENTITY_SESSION_INDEX}"))
                    definition = {
                        "non_unique": "CREATE INDEX {name} ON identity_verifications(provider, provider_reference_id)",
                        "wrong_columns": "CREATE UNIQUE INDEX {name} ON identity_verifications(user_id, provider_reference_id)",
                        "partial": "CREATE UNIQUE INDEX {name} ON identity_verifications(provider, provider_reference_id) WHERE status='VERIFIED'",
                    }[fault]
                    await connection.execute(text(definition.format(name=IDENTITY_SESSION_INDEX)))
                    now = datetime.now(UTC).isoformat()
                    for user in users:
                        await connection.execute(
                            insert(identity_verifications).values(
                                id=str(uuid4()),
                                user_id=user,
                                status="REVIEW_REQUIRED",
                                provider="hmac-reference",
                                provider_reference_id="same-external-session",
                                created_at=now,
                                updated_at=now,
                            )
                        )
                refused = False
                try:
                    await assert_runtime_schema_compatible(engine)
                except RuntimeError as exc:
                    assert "uniqueness" in str(exc), "An unrelated startup error is not index proof"
                    refused = True
                # Neither repair nor refusal may silently delete conflicting
                # identity evidence to satisfy the uniqueness contract.
                async with engine.raw.connect() as connection:
                    assert (
                        await connection.scalar(
                            text(
                                "SELECT count(*) FROM identity_verifications WHERE provider_reference_id='same-external-session'"
                            )
                        )
                        == 2
                    )
                assert refused, (
                    "Startup accepted duplicate provider sessions behind an ineffective named index"
                )
            finally:
                await engine.close()
