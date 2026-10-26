# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Disposable provisioning infrastructure for the real customer browser harness.

No tenant, identity, session or READY state is seeded. Not production enrollment.
"""

import os
from contextlib import AsyncExitStack, asynccontextmanager

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import text
from tests.stage3_controller_helpers import controller_process

from responsibleai.data_governance.backup_defense import SqliteDurableLifecycleStateProvider
from responsibleai.data_governance.provisioning_manifest import ProvisionerTrust
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
from responsibleai.environment import is_production


@asynccontextmanager
async def isolated_provisioning_controller(database, *, authorized_bootstrap=False):
    if is_production():
        raise RuntimeError("Disposable controller cannot run in production")
    engine = create_engine(database)
    try:
        if engine.raw.dialect.name != "postgresql":
            raise RuntimeError("Customer qualification requires PostgreSQL")
        async with engine.raw.connect() as connection:
            if await connection.scalar(text("SELECT count(*) FROM organizations")):
                raise RuntimeError("Disposable controller requires a fresh tenant database")
            identity = await postgres_identity(connection)
        provider = SqliteDurableLifecycleStateProvider(
            os.environ["WHITEPACT_STORE_B_PATH"], secret_key=os.environ["WHITEPACT_STORE_B_KEY"]
        )
        if provider.get_readiness_state() is not None or provider.list_all():
            raise RuntimeError("Existing readiness/lifecycle evidence cannot be reset")
        key = Ed25519PrivateKey.generate()
        trust = ProvisionerTrust(
            "disposable-browser-controller",
            key.public_key().public_bytes_raw(),
            "disposable-browser-qualification",
            "development",
            identity,
            store_b_identity(provider),
        )
        async with AsyncExitStack() as installation:
            if authorized_bootstrap:
                from scripts.engineering.m13_bootstrap_customer_fixture import (
                    authorized_disposable_installation,
                )

                await installation.enter_async_context(
                    authorized_disposable_installation(
                        engine, provider, deployment_id=trust.deployment_id
                    )
                )
            PendingTenantReservations(provider).initialize()
            PublicationAuthorizationLedger(provider).initialize(trust)
            service = ProtectedTenantController(engine, provider, trust, key)
            with pytest.MonkeyPatch.context() as environment:
                environment.setenv("WHITEPACT_ENV", "development")
                async with controller_process(service, environment):
                    yield service
    finally:
        await engine.close()
