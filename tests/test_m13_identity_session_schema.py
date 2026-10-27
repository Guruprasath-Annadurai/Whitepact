# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""0067 stays the accepted schema. Session uniqueness does not advance it."""

from __future__ import annotations

import uuid
from contextlib import aclosing
from datetime import UTC, datetime

import pytest
from sqlalchemy import insert, text

from responsibleai.db.engine import create_engine, identity_verifications
from responsibleai.db.identity_session_uniqueness import (
    IDENTITY_SESSION_INDEX,
    IdentitySessionConflictError,
    IdentitySessionIndexInvalidError,
    ensure_identity_session_uniqueness,
)
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from responsibleai.db.runtime_compatibility import assert_runtime_schema_compatible
from responsibleai.db.web_identity_repository import WebIdentityRepository
from tests.pg_test_url import isolated_pg_url


async def _index_present(engine) -> bool:
    async with engine.raw.connect() as connection:
        found = await connection.scalar(
            text("SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname=:name"),
            {"name": IDENTITY_SESSION_INDEX},
        )
    return bool(found)


@pytest.mark.asyncio
async def test_upgrade_head_stays_0067_and_installs_unique_sessions() -> None:
    async with aclosing(isolated_pg_url("m13schema")) as databases:
        async for database in databases:
            await _run_alembic(_find_alembic_ini(), _migration_env(database), "upgrade", "head")
            engine = create_engine(database)
            try:
                async with engine.raw.connect() as connection:
                    versions = (
                        (await connection.execute(text("SELECT version_num FROM alembic_version")))
                        .scalars()
                        .all()
                    )
                assert versions == ["0067"]
                assert await _index_present(engine)
                await assert_runtime_schema_compatible(engine)
                await assert_runtime_schema_compatible(engine)
            finally:
                await engine.raw.dispose()


@pytest.mark.asyncio
async def test_duplicate_provider_sessions_block_the_index_and_remain() -> None:
    async with aclosing(isolated_pg_url("m13dup")) as databases:
        async for database in databases:
            await _run_alembic(_find_alembic_ini(), _migration_env(database), "upgrade", "head")
            engine = create_engine(database)
            try:
                async with engine.raw.begin() as connection:
                    await connection.execute(text(f"DROP INDEX IF EXISTS {IDENTITY_SESSION_INDEX}"))
                web = WebIdentityRepository(engine)
                user_id, _token = await web.register(
                    "Human", "dup@example.com", "correct-horse-battery-staple-9"
                )
                now = datetime.now(UTC).isoformat()
                async with engine.raw.begin() as connection:
                    for _ in range(2):
                        await connection.execute(
                            insert(identity_verifications).values(
                                id=str(uuid.uuid4()),
                                user_id=user_id,
                                status="REVIEW_REQUIRED",
                                provider="hmac-reference",
                                provider_reference_id="sess_conflict",
                                created_at=now,
                                updated_at=now,
                            )
                        )
                with pytest.raises(IdentitySessionConflictError):
                    await ensure_identity_session_uniqueness(engine)
                async with engine.raw.connect() as connection:
                    count = await connection.scalar(
                        text("SELECT count(*) FROM identity_verifications")
                    )
                assert count == 2
                assert await _index_present(engine) is False
                with pytest.raises(RuntimeError, match="uniqueness"):
                    await assert_runtime_schema_compatible(engine)
                async with engine.raw.connect() as connection:
                    count_after = await connection.scalar(
                        text("SELECT count(*) FROM identity_verifications")
                    )
                assert count_after == 2
            finally:
                await engine.raw.dispose()


@pytest.mark.asyncio
async def test_incompatible_named_index_is_left_in_place_and_startup_rolls_back() -> None:
    async with aclosing(isolated_pg_url("m13badidx")) as databases:
        async for database in databases:
            await _run_alembic(_find_alembic_ini(), _migration_env(database), "upgrade", "head")
            engine = create_engine(database)
            try:
                async with engine.raw.begin() as connection:
                    await connection.execute(text(f"DROP INDEX {IDENTITY_SESSION_INDEX}"))
                    await connection.execute(
                        text(
                            f"CREATE INDEX {IDENTITY_SESSION_INDEX} "
                            "ON identity_verifications (provider)"
                        )
                    )
                with pytest.raises(IdentitySessionIndexInvalidError):
                    await ensure_identity_session_uniqueness(engine)
                async with engine.raw.connect() as connection:
                    definition = await connection.scalar(
                        text("SELECT indexdef FROM pg_indexes WHERE indexname=:name"),
                        {"name": IDENTITY_SESSION_INDEX},
                    )
                    version = await connection.scalar(
                        text("SELECT version_num FROM alembic_version")
                    )
                assert definition.startswith("CREATE INDEX")
                assert "UNIQUE" not in definition
                assert version == "0067"
                with pytest.raises(RuntimeError, match="uniqueness"):
                    await assert_runtime_schema_compatible(engine)
                async with engine.raw.connect() as connection:
                    still = await connection.scalar(
                        text("SELECT indexdef FROM pg_indexes WHERE indexname=:name"),
                        {"name": IDENTITY_SESSION_INDEX},
                    )
                assert still == definition
            finally:
                await engine.raw.dispose()
