# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Repository metadata/tenant regressions, not customer authority acceptance."""

import asyncio
from contextlib import aclosing

import pytest

from responsibleai.db.engine import create_engine, organizations
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from responsibleai.trust_fabric.directory import PrincipalDirectory
from responsibleai.trust_fabric.enums import IdentifierType, PrincipalType
from responsibleai.trust_fabric.errors import CrossTenantAccessError, IdentifierCollisionError
from tests.pg_test_url import isolated_pg_url


@pytest.fixture(params=["sqlite", "postgres"])
async def directory(request, tmp_path):
    async def prepare(url):
        engine = create_engine(url)
        if request.param == "sqlite":
            await engine.init()
        async with engine.raw.begin() as connection:
            await connection.execute(
                organizations.insert(),
                [
                    {"id": "apex-org", "name": "APEX", "slug": "apex", "created_at": "now"},
                    {"id": "other-org", "name": "Other", "slug": "other", "created_at": "now"},
                ],
            )
        return engine

    if request.param == "postgres":
        async with aclosing(isolated_pg_url("wp_apex_directory")) as databases:
            async for url in databases:
                ini = _find_alembic_ini()
                assert ini is not None
                await _run_alembic(ini, _migration_env(url), "upgrade", "head")
                engine = await prepare(url)
                try:
                    yield PrincipalDirectory(engine)
                finally:
                    await engine.close()
    else:
        engine = await prepare(f"sqlite+aiosqlite:///{tmp_path}/directory.db")
        try:
            yield PrincipalDirectory(engine)
        finally:
            await engine.close()


@pytest.mark.asyncio
async def test_metadata_survives_all_directory_read_paths(directory):
    metadata = {"environment": "local", "labels": ["customer-created"]}
    principal = await directory.create_principal(
        org_id="apex-org",
        principal_type=PrincipalType.AI_AGENT,
        display_name="APEX descriptive agent",
        metadata=metadata,
    )
    await directory.attach_identifier(
        org_id="apex-org",
        principal_id=principal.id,
        identifier_type=IdentifierType.EMAIL,
        value="apex@example.com",
    )
    direct = await directory.get_principal(principal.id, org_id="apex-org")
    resolved = await directory.resolve_by_identifier(
        org_id="apex-org", identifier_type=IdentifierType.EMAIL, value="APEX@EXAMPLE.COM"
    )
    searched = await directory.search_principals(org_id="apex-org", query="descriptive")
    assert direct.metadata == metadata
    assert resolved is not None and resolved.metadata == metadata
    assert len(searched) == 1 and searched[0].metadata == metadata
    with pytest.raises(CrossTenantAccessError):
        await directory.get_principal(principal.id, org_id="other-org")
    assert await directory.search_principals(org_id="other-org", query="descriptive") == []


@pytest.mark.asyncio
async def test_concurrent_identifier_claim_has_one_winner_without_authority_transfer(directory):
    principals = [
        await directory.create_principal(
            org_id="apex-org", principal_type=PrincipalType.AI_AGENT, display_name=f"Agent {index}"
        )
        for index in range(4)
    ]
    claims = await asyncio.gather(
        *[
            directory.attach_identifier(
                org_id="apex-org",
                principal_id=principal.id,
                identifier_type=IdentifierType.EMAIL,
                value="same@example.com",
            )
            for principal in principals
        ],
        return_exceptions=True,
    )
    assert sum(not isinstance(item, Exception) for item in claims) == 1
    assert sum(isinstance(item, IdentifierCollisionError) for item in claims) == 3
    resolved = await directory.resolve_by_identifier(
        org_id="apex-org", identifier_type=IdentifierType.EMAIL, value="same@example.com"
    )
    assert resolved is not None
    assert resolved.lifecycle_state.value == "PENDING_VERIFICATION"
