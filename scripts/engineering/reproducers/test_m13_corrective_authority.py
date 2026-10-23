# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Additional independent acceptance gates; original reproducers remain unchanged."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import tempfile
import threading
import uuid
from contextlib import aclosing, asynccontextmanager
from pathlib import Path
from unittest.mock import patch

import asyncpg
import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from scripts.engineering.m13i1_customer_journey import serve
from scripts.engineering.m13i2_customer_journey import configured_settings
from sqlalchemy import text
from tests.m13_owner_qualification import qualify_owner, root_completion_assertion
from tests.pg_test_url import isolated_pg_url
from tests.stage3_controller_helpers import controller_process
from tests.test_stage3_controller_postgres import isolated_controller_context

import responsibleai.dashboard.app as dashboard
from responsibleai.data_governance.tenant_client import TenantCreationDeniedError
from responsibleai.db.migrate import MigrationError, _find_alembic_ini, _migration_env, _run_alembic
from responsibleai.enterprise.authority.service import CustomerAuthorityService
from responsibleai.enterprise.errors import EnterpriseError
from responsibleai.enterprise.service import Actor, EnterpriseIAM
from responsibleai.isolation.container_backend import DockerContainerBackend
from responsibleai.rbac.models import Role


@pytest.mark.asyncio
async def test_unverified_owner_cannot_activate_root_with_default_flags() -> None:
    """Historical public test ID now explicitly executes both approved successors.

    Original function remains immutable in Git blob
    30a18aa17fc2aa0d67bb7ca5a7f9e757985192f3 at e156b59a.
    The two paths below are not represented as the same threat scenario.
    """
    await _assert_never_verified_onboarding_denied()
    await _assert_revoked_verification_root_denied()


@asynccontextmanager
async def protected_root_fixture():
    with tempfile.TemporaryDirectory(prefix="wp-root-disposition-") as directory:
        with pytest.MonkeyPatch.context() as environment:
            async with isolated_controller_context(
                Path(directory), environment, "wp_apex_unverified_authority"
            ) as value:
                async with controller_process(value[0], environment):
                    yield value


async def _assert_no_root_effects(engine):
    async with engine.raw.connect() as connection:
        assert (
            await connection.scalar(text("SELECT count(*) FROM governance_root_authority_records"))
            == 0
        )
        assert await connection.scalar(text("SELECT count(*) FROM trust_fabric_principals")) == 0


async def _assert_never_verified_onboarding_denied():
    async with protected_root_fixture() as (controller, identities, _, _, _):
        engine = controller.engine
        user_id, _ = await identities.register(
            "Never verified", f"pending-{uuid.uuid4().hex}@example.com", "Local-Only-Strong-42!"
        )
        token, csrf = await identities.create_session(user_id)
        with pytest.raises(TenantCreationDeniedError):
            await EnterpriseIAM(engine).create_workspace(
                actor_user_id=user_id,
                name="Denied",
                slug=f"q-{uuid.uuid4().hex}",
                kind="ORGANIZATION",
                session_token=token,
                csrf=csrf,
            )
        async with engine.raw.connect() as connection:
            assert await connection.scalar(text("SELECT count(*) FROM organizations")) == 0
            assert (
                await connection.scalar(text("SELECT count(*) FROM tenant_provisioning_records"))
                == 0
            )
        assert controller.provider.list_all() == []
        await _assert_no_root_effects(engine)


async def _assert_revoked_verification_root_denied():
    async with protected_root_fixture() as (controller, _, user_id, token, csrf):
        engine = controller.engine
        org = await EnterpriseIAM(engine).create_workspace(
            actor_user_id=user_id,
            name="Qualification",
            slug=f"q-{uuid.uuid4().hex}",
            kind="ORGANIZATION",
            session_token=token,
            csrf=csrf,
        )
        org_id = org["id"]
        assert (
            controller.ledger.completion(org_id).generation_id
            == controller.provider.get_state(org_id).generation_id
        )
        actor = Actor("USER", user_id, user_id, org_id, Role.OWNER, "ACTIVE")
        actor, owner_key, credential = await qualify_owner(engine, actor)
        service = CustomerAuthorityService(engine)
        ceremony = await service.initiate_root_bootstrap(actor, org_id=org_id)
        key = Ed25519PrivateKey.generate()
        public = key.public_key().public_bytes_raw().hex()
        assertion = await root_completion_assertion(
            service, actor, ceremony, public, owner_key, credential
        )
        async with engine.raw.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE web_users SET email_verified_at=NULL,verification_status='UNVERIFIED' WHERE id=:user"
                ),
                {"user": user_id},
            )
        message = f"WP_ROOT_POP:{org_id}:{ceremony['nonce']}:{hashlib.sha256(ceremony['token'].encode()).hexdigest()}"
        with pytest.raises(EnterpriseError) as denied:
            await service.complete_root_bootstrap(
                actor,
                org_id=org_id,
                token=ceremony["token"],
                nonce=ceremony["nonce"],
                root_public_key=public,
                root_signature=base64.urlsafe_b64encode(key.sign(message.encode()))
                .rstrip(b"=")
                .decode(),
                scope_description="Local qualification",
                purpose="Revoked verification rejection",
                allowed_action_types=["test.harmless"],
                allowed_targets=["local:qualification"],
                webauthn_assertion=assertion,
            )
        assert denied.value.code == "IDENTITY_ASSURANCE_REQUIRED"
        await _assert_no_root_effects(engine)


@pytest.mark.asyncio
async def test_unverified_onboarding_successor_has_no_tenant_or_root():
    await _assert_never_verified_onboarding_denied()


@pytest.mark.asyncio
async def test_unverified_after_provisioning_successor_has_no_root():
    await _assert_revoked_verification_root_denied()


@pytest.mark.asyncio
async def test_cleanup_error_does_not_erase_requested_cancellation() -> None:
    backend = DockerContainerBackend()
    started, release = threading.Event(), threading.Event()
    errors = []

    def failed_cleanup(*args, **kwargs):
        started.set()
        assert release.wait(5), "test cleanup release timed out"
        raise RuntimeError("containment unconfirmed")

    async def execution_owner():
        try:
            await backend._remove_containers_uninterruptible(
                ["wp_owned_execution"], stable_seconds=0, wait_seconds=0.01
            )
        except RuntimeError as error:
            errors.append(str(error))
        await asyncio.sleep(0)
        return "resumed after cancellation"

    with patch.object(backend, "_remove_containers", side_effect=failed_cleanup):
        task = asyncio.create_task(execution_owner())
        try:
            assert await asyncio.to_thread(started.wait, 3)
            task.cancel()
            await asyncio.sleep(0)
            release.set()
            try:
                await task
            except asyncio.CancelledError:
                pass
            assert errors == ["containment unconfirmed"]
            assert task.cancelled(), "Cleanup error handling must not erase execution cancellation"
        finally:
            release.set()


@pytest.mark.asyncio
async def test_mandatory_passkey_requirement_prevents_intermediate_0064_schema() -> None:
    async with aclosing(isolated_pg_url("wp_apex_downgrade_guard")) as databases:
        async for database in databases:
            ini = _find_alembic_ini()
            assert ini is not None
            env = _migration_env(database)
            await _run_alembic(ini, env, "upgrade", "0065")
            connection = await asyncpg.connect(database)
            try:
                await connection.execute(
                    "INSERT INTO organizations(id,name,slug,created_at) VALUES('guard','guard','guard','2026-01-01')"
                )
                await connection.execute(
                    "INSERT INTO trust_fabric_bootstrap_records(id,org_id,token_hash,expires_at,nonce,created_at,require_passkey_stepup) VALUES('guard','guard','hash','2099-01-01','nonce','2026-01-01',1)"
                )
                try:
                    await _run_alembic(ini, env, "downgrade", "0064")
                except MigrationError:
                    pass
                revision = await connection.fetchval("SELECT version_num FROM alembic_version")
                assert revision == "0065", (
                    "Retention metadata must not permit a 0064 runtime while a mandatory passkey ceremony exists"
                )
                assert (
                    await connection.fetchval(
                        "SELECT require_passkey_stepup FROM trust_fabric_bootstrap_records WHERE id='guard'"
                    )
                    == 1
                )
            finally:
                await connection.close()


@pytest.mark.asyncio
async def test_revision_0064_must_not_serve_while_mandatory_requirements_are_retained() -> None:
    async with aclosing(isolated_pg_url("wp_apex_retention_runtime")) as databases:
        async for database in databases:
            ini = _find_alembic_ini()
            assert ini is not None
            env = _migration_env(database)
            await _run_alembic(ini, env, "upgrade", "head")
            connection = await asyncpg.connect(database)
            try:
                await connection.execute(
                    "INSERT INTO organizations(id,name,slug,created_at) VALUES('retained','retained','retained','2026-01-01')"
                )
                await connection.execute(
                    "INSERT INTO trust_fabric_bootstrap_records(id,org_id,token_hash,expires_at,nonce,created_at,require_passkey_stepup) VALUES('retained','retained','hash','2099-01-01','nonce','2026-01-01',1)"
                )
                try:
                    await _run_alembic(ini, env, "downgrade", "0064")
                except MigrationError:
                    assert (
                        await connection.fetchval("SELECT version_num FROM alembic_version")
                        == "0065"
                    )
                    return
                assert (
                    await connection.fetchval(
                        "SELECT require_passkey_stepup FROM _alembic_0065_downgrade_retention WHERE id='retained'"
                    )
                    == 1
                )
                with configured_settings(
                    {
                        "database_url": database,
                        "auto_migrate": False,
                        "auth_enabled": True,
                        "api_keys": [],
                        "environment": "development",
                    }
                ):
                    async with serve(dashboard.app) as origin:
                        async with httpx.AsyncClient() as client:
                            response = await client.get(f"{origin}/login")
                            assert response.status_code == 503, (
                                "Application completed startup and served HTTP200 at0064 while mandatory requirements existed only in retention metadata"
                            )
            finally:
                await connection.close()
