# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Actual PostgreSQL/Store B controller tests, not HTTP/production qualification."""

import asyncio
import secrets
import sqlite3
import uuid
from contextlib import asynccontextmanager

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import text

from responsibleai.data_governance.backup_defense import (
    RestoreReadinessState,
    SqliteDurableLifecycleStateProvider,
)
from responsibleai.data_governance.provisioning_manifest import (
    ProvisionerTrust,
    ProvisioningAuthorizationError,
)
from responsibleai.data_governance.tenant_controller import (
    ProtectedTenantController,
    postgres_identity,
    store_b_identity,
)
from responsibleai.data_governance.tenant_provisioning import (
    PendingTenantReservations,
    PublicationAuthorizationLedger,
)
from responsibleai.db.engine import create_engine
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from responsibleai.db.web_identity_repository import WebIdentityRepository
from tests.pg_test_url import isolated_pg_url


@pytest.fixture
async def controller(tmp_path, monkeypatch, request):
    prefix = getattr(request.module, "CONTROLLER_DATABASE_PREFIX", "wp_stage3_controller")
    async with isolated_controller_context(tmp_path, monkeypatch, prefix) as value:
        yield value


@asynccontextmanager
async def isolated_controller_context(tmp_path, monkeypatch, prefix="wp_stage3_controller"):
    """Use signed installation in hosted mode, not a direct initial READY write."""
    monkeypatch.setenv("WHITEPACT_ENV", "staging")
    async for url in isolated_pg_url(prefix):
        await _run_alembic(_find_alembic_ini(), _migration_env(url), "upgrade", "0067")
        engine = create_engine(url)
        from contextlib import AsyncExitStack

        installation = AsyncExitStack()
        try:
            provider = SqliteDurableLifecycleStateProvider(
                tmp_path / "b.sqlite3", secret_key=secrets.token_hex(32)
            )
            from scripts.engineering.m13_bootstrap_customer_fixture import (
                authorized_disposable_installation,
            )

            await installation.enter_async_context(
                authorized_disposable_installation(
                    engine, provider, deployment_id="stage3-isolated", environment="staging"
                )
            )
            key = Ed25519PrivateKey.generate()
            async with engine.raw.connect() as connection:
                pg = await postgres_identity(connection)
            trust = ProvisionerTrust(
                "disposable-controller",
                key.public_key().public_bytes_raw(),
                "stage3-isolated",
                "staging",
                pg,
                store_b_identity(provider),
            )
            PendingTenantReservations(provider).initialize()
            PublicationAuthorizationLedger(provider).initialize(trust)
            identity = WebIdentityRepository(engine)
            user, verification = await identity.register(
                "Isolated Owner", f"{uuid.uuid4().hex}@example.test", "Independent-Test-Only-42!"
            )
            assert await identity.verify_email(verification)
            token, csrf = await identity.create_session(user)
            yield (
                ProtectedTenantController(engine, provider, trust, key),
                identity,
                user,
                token,
                csrf,
            )
        finally:
            await installation.aclose()
            await engine.close()


@pytest.mark.asyncio
async def test_real_controller_creates_matching_complete_stores_and_idempotent_retry(controller):
    service, identity, user, token, csrf = controller
    operation = dict(
        session_token=token,
        csrf=csrf,
        request_id="genuine-request-1",
        name="Isolated Tenant",
        slug="isolated-tenant",
        attach_session=True,
    )
    tenant = await service.create(**operation)
    assert await service.create(**operation) == tenant
    lifecycle = service.provider.get_state(tenant)
    complete = service.ledger.completion(tenant)
    assert complete.generation_id == lifecycle.generation_id
    assert lifecycle.state.value == "ACTIVE"
    async with service.engine.raw.connect() as connection:
        row = (
            (
                await connection.execute(
                    text(
                        "SELECT p.*,o.owner_user_id,o.governance_status FROM tenant_provisioning_records p "
                        "JOIN organizations o ON o.id=p.tenant_id WHERE tenant_id=:tenant"
                    ),
                    {"tenant": tenant},
                )
            )
            .mappings()
            .one()
        )
        assert row["principal_id"] == row["owner_user_id"] == user
        assert row["state"] == "COMPLETE"
        assert row["governance_status"] == "ACTIVE"
        assert row["completion_digest"] == complete.completion_digest
        assert row["generation_id"] == lifecycle.generation_id
        assert await connection.scalar(text("SELECT count(*) FROM organizations")) == 1
    assert (await identity.get_principal(token)).org_id == tenant
    with sqlite3.connect(service.provider.path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM tenant_provisioning_reservations"
        ).fetchone() == (1,)


@pytest.mark.asyncio
async def test_invalid_credentials_do_not_reserve_or_create_authority(controller):
    service, _, _, token, csrf = controller
    for bad_token, bad_csrf in (("forged", csrf), (token, "forged"), ("", "")):
        with pytest.raises(ProvisioningAuthorizationError):
            await service.create(
                session_token=bad_token,
                csrf=bad_csrf,
                request_id="invalid",
                name="Denied",
                slug="denied",
            )
    assert service.provider.list_all() == []
    async with service.engine.raw.connect() as connection:
        assert await connection.scalar(text("SELECT count(*) FROM organizations")) == 0
    with sqlite3.connect(service.provider.path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM tenant_provisioning_reservations"
        ).fetchone() == (0,)


@pytest.mark.asyncio
async def test_failed_readiness_never_recovers_through_tenant_creation(controller):
    service, _, _, token, csrf = controller
    service.provider.set_readiness_state(RestoreReadinessState.FAILED)
    with pytest.raises(ProvisioningAuthorizationError, match="quarantined"):
        await service.create(
            session_token=token, csrf=csrf, request_id="failed", name="Denied", slug="denied"
        )
    assert service.provider.get_readiness_state() == RestoreReadinessState.FAILED
    assert service.provider.list_all() == []


@pytest.mark.asyncio
async def test_concurrent_retries_publish_one_generation_and_completion(controller):
    service, _, _, token, csrf = controller
    operation = dict(
        session_token=token,
        csrf=csrf,
        request_id="concurrent-request",
        name="Concurrent Tenant",
        slug="concurrent-tenant",
    )
    results = await asyncio.gather(*(service.create(**operation) for _ in range(8)))
    assert len(set(results)) == 1
    tenant = results[0]
    assert (
        service.ledger.completion(tenant).generation_id
        == service.provider.get_state(tenant).generation_id
    )
    async with service.engine.raw.connect() as connection:
        for table in ("organizations", "tenant_provisioning_records", "tenant_provisioning_outbox"):
            assert await connection.scalar(text(f"SELECT count(*) FROM {table}")) == 1
    with sqlite3.connect(service.provider.path) as connection:
        for table in (
            "tenant_provisioning_reservations",
            "provisioning_publication_consumptions",
            "tenant_provisioning_completions",
        ):
            assert connection.execute(f"SELECT count(*) FROM {table}").fetchone() == (1,)
