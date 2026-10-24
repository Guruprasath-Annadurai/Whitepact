# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Disposable PostgreSQL component tenants for suites that establish organizations.

Store B READY here is the existing structural component fixture used by Stage 3
controller tests. It is not first-deployment bootstrap, customer acceptance,
or a production credential. Paid plans are applied only through the separate
monotonic billing transition after FREE protected creation.
"""

from __future__ import annotations

import asyncio
import os
import secrets
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from responsibleai.data_governance.backup_defense import (
    RestoreReadinessState,
    SqliteDurableLifecycleStateProvider,
)
from responsibleai.data_governance.provisioning_manifest import ProvisionerTrust
from responsibleai.data_governance.tenant_client import TenantCreationDeniedError
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
from responsibleai.db.org_repository import OrgRepository, SetPlanStatus
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.service import EnterpriseIAM
from responsibleai.rbac.models import Plan
from tests.pg_test_url import database_url, drop_isolated_database, resolve_admin_url
from tests.stage3_controller_helpers import controller_process

_TEMPLATE_LOCK = asyncio.Lock()
_TEMPLATE_NAME: str | None = None


async def _migrated_template_name() -> str:
    """One migrated PostgreSQL 16 template so each fixture is not a full upgrade."""
    global _TEMPLATE_NAME
    async with _TEMPLATE_LOCK:
        if _TEMPLATE_NAME is not None:
            return _TEMPLATE_NAME
        import asyncpg

        admin = await resolve_admin_url()
        name = f"wp_component_template_{os.urandom(4).hex()}"
        connection = await asyncpg.connect(admin)
        try:
            await connection.execute(f'CREATE DATABASE "{name}"')
        finally:
            await connection.close()
        url = database_url(admin, name)
        engine = create_engine(url)
        try:
            await _run_alembic(_find_alembic_ini(), _migration_env(url), "upgrade", "0067")
        finally:
            await engine.close()
        _TEMPLATE_NAME = name
        return name


@asynccontextmanager
async def attach_component_controller(engine, tmp_path, monkeypatch):
    """Bind a protected controller process to an already migrated database."""
    monkeypatch.setenv("WHITEPACT_ENV", "staging")
    provider = SqliteDurableLifecycleStateProvider(
        tmp_path / "component-store-b.sqlite3", secret_key=secrets.token_hex(32)
    )
    provider.set_readiness_state(RestoreReadinessState.READY)
    key = Ed25519PrivateKey.generate()
    async with engine.raw.connect() as connection:
        identity = await postgres_identity(connection)
    trust = ProvisionerTrust(
        "disposable-controller",
        key.public_key().public_bytes_raw(),
        "stage3-isolated",
        "staging",
        identity,
        store_b_identity(provider),
    )
    PendingTenantReservations(provider).initialize()
    PublicationAuthorizationLedger(provider).initialize(trust)
    controller = ProtectedTenantController(engine, provider, trust, key)
    from responsibleai.data_governance.backup_defense import (
        RestoreReadinessGate,
        get_restore_readiness_gate,
        set_restore_readiness_gate,
    )

    previous_gate = get_restore_readiness_gate()
    set_restore_readiness_gate(RestoreReadinessGate(provider=provider, db_engine=engine))
    monkeypatch.setenv("WHITEPACT_STORE_B_PATH", str(provider.path))
    monkeypatch.setenv("WHITEPACT_STORE_B_KEY", provider._secret_key)
    try:
        async with controller_process(controller, monkeypatch):
            yield controller
    finally:
        set_restore_readiness_gate(previous_gate)


@asynccontextmanager
async def component_controller(tmp_path, monkeypatch, prefix: str):
    """Fresh PostgreSQL database plus the protected provisioning process."""
    import asyncpg

    admin = await resolve_admin_url()
    template = await _migrated_template_name()
    name = f"{prefix}_{os.urandom(4).hex()}"
    if len(name) > 63:
        raise ValueError("Component database prefix is too long")
    connection = await asyncpg.connect(admin)
    try:
        await connection.execute(f'CREATE DATABASE "{name}" TEMPLATE "{template}"')
    finally:
        await connection.close()
    engine = create_engine(database_url(admin, name))
    try:
        async with attach_component_controller(engine, tmp_path, monkeypatch) as controller:
            yield controller
    finally:
        await engine.close()
        await drop_isolated_database(admin, name)


async def provision_component_organization(
    engine,
    *,
    name: str,
    slug: str,
    plan: Plan = Plan.FREE,
    monthly_budget_usd: float = 10_000.0,
):
    """Verified human session, protected FREE creation, then optional billing transition."""
    if plan != Plan.FREE:
        # Creation itself must still refuse a paid plan. Prove that, then transition.
        try:
            await OrgRepository(engine).create_org(name, slug, plan=plan)
        except TenantCreationDeniedError as exc:
            if "paid entitlement" not in str(exc):
                raise
        else:
            raise AssertionError("Tenant creation accepted a paid entitlement")
    identity = WebIdentityRepository(engine)
    user, verification = await identity.register(
        "Component Owner",
        f"component-{uuid.uuid4().hex}@example.test",
        "Independent-Test-Only-42!",
    )
    assert await identity.verify_email(verification)
    token, csrf = await identity.create_session(user)
    org = await OrgRepository(engine).create_org(
        name,
        slug,
        monthly_budget_usd=monthly_budget_usd,
        session_token=token,
        csrf=csrf,
        request_id=f"cmp-{uuid.uuid4().hex}",
    )
    if plan != Plan.FREE:
        applied = await OrgRepository(engine).set_plan_status(
            org.id, plan, event_timestamp=datetime.now(UTC).isoformat()
        )
        if applied is not SetPlanStatus.APPLIED:
            raise RuntimeError(f"Component entitlement transition was {applied.value}")
        upgraded = await OrgRepository(engine).get_org(org.id)
        if upgraded is None or upgraded.plan is not plan:
            raise RuntimeError("Component entitlement was not stored")
        return upgraded
    return org


async def authorized_workspace(
    engine,
    actor_user_id: str,
    *,
    name: str,
    slug: str,
    kind: str = "ORGANIZATION",
):
    """Session bound to the same verified user the workspace names as creator."""
    token, csrf = await WebIdentityRepository(engine).create_session(actor_user_id)
    return await EnterpriseIAM(engine).create_workspace(
        actor_user_id=actor_user_id,
        name=name,
        slug=slug,
        kind=kind,
        session_token=token,
        csrf=csrf,
        request_id=f"ws-{uuid.uuid4().hex}",
    )
