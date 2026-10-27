# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Concurrent root completion with real PostgreSQL and verified WebAuthn ceremonies."""

import asyncio
import uuid

import pytest
from sqlalchemy import func, select

from responsibleai.db.engine import governance_root_authority_records
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.authority.errors import (
    BOOTSTRAP_TOKEN_INVALID,
    BOOTSTRAP_TOKEN_REPLAY,
    ROOT_ALREADY_EXISTS,
    WEBAUTHN_ASSERTION_INVALID,
)
from responsibleai.enterprise.authority.service import CustomerAuthorityService
from responsibleai.enterprise.errors import EnterpriseError
from responsibleai.enterprise.service import Actor
from responsibleai.rbac.models import Role
from tests.m13_owner_qualification import qualify_owner, root_completion_assertion
from tests.pg_test_url import isolated_pg_url
from tests.protected_component_tenant import (
    authorized_workspace,
    bind_component_controller_scope,
    create_controlled_engine,
)
from tests.test_m12fs_root_hardening import _fresh_root_proof


@pytest.fixture(autouse=True)
async def _component_controller_scope(tmp_path, monkeypatch):
    async with bind_component_controller_scope(tmp_path, monkeypatch):
        yield


async def _complete_after(release, service, actor, parameters):
    await release.wait()
    return await service.complete_root_bootstrap(actor, **parameters)


@pytest.mark.asyncio
async def test_independent_operation_bound_completions_commit_only_one_root():
    async for url in isolated_pg_url("wp_convergence_root_race"):
        await _run_alembic(_find_alembic_ini(), _migration_env(url), "upgrade", "head")
        engine = await create_controlled_engine(url)
        try:
            identities = WebIdentityRepository(engine)
            user, token = await identities.register(
                "Concurrent owner", f"concurrent-{uuid.uuid4().hex}@example.com", "Local-Strong-42!"
            )
            await identities.verify_email(token)
            org = await authorized_workspace(
                engine,
                user,
                name="Concurrent root",
                slug=uuid.uuid4().hex,
                kind="ORGANIZATION",
            )
            actor = Actor(
                actor_type="USER",
                actor_id=user,
                user_id=user,
                org_id=org["id"],
                role=Role.OWNER,
                membership_status="ACTIVE",
            )
            actor, key, credential = await qualify_owner(engine, actor)
            service = CustomerAuthorityService(engine)
            calls = []
            ceremony = await service.initiate_root_bootstrap(actor, org_id=actor.org_id)
            for sign_count in (2, 3):
                public, signature = _fresh_root_proof(actor.org_id, ceremony)
                assertion = await root_completion_assertion(
                    service, actor, ceremony, public, key, credential, sign_count=sign_count
                )
                calls.append(
                    dict(
                        org_id=actor.org_id,
                        token=ceremony["token"],
                        nonce=ceremony["nonce"],
                        root_public_key=public,
                        root_signature=signature,
                        webauthn_assertion=assertion,
                        scope_description="Concurrent qualification",
                        purpose="Harmless test",
                        allowed_action_types=["test.harmless"],
                        allowed_targets=["local:qualification"],
                    )
                )
            release = asyncio.Event()

            tasks = [
                asyncio.create_task(_complete_after(release, service, actor, parameters))
                for parameters in calls
            ]
            release.set()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            successes = [result for result in results if isinstance(result, dict)]
            failures = [result for result in results if isinstance(result, BaseException)]
            assert len(successes) == len(failures) == 1
            assert successes[0]["status"] == "BOOTSTRAPPED"
            assert isinstance(failures[0], EnterpriseError)
            assert failures[0].code in {
                BOOTSTRAP_TOKEN_INVALID,
                ROOT_ALREADY_EXISTS,
                BOOTSTRAP_TOKEN_REPLAY,
                WEBAUTHN_ASSERTION_INVALID,
            }
            async with engine.raw.connect() as conn:
                count = await conn.scalar(
                    select(func.count())
                    .select_from(governance_root_authority_records)
                    .where(governance_root_authority_records.c.organization_id == actor.org_id)
                )
            assert count == 1
        finally:
            await engine.close()
