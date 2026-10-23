# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Abrupt child-process exits at real PG/SQLite provisioning commit boundaries."""

import asyncio
import multiprocessing
import os
import sqlite3
from contextlib import asynccontextmanager

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import text

from responsibleai.data_governance.backup_defense import (
    RestoreReadinessState,
    SqliteDurableLifecycleStateProvider,
)
from responsibleai.data_governance.tenant_controller import ProtectedTenantController
from responsibleai.db.engine import create_engine
from tests.test_stage3_controller_postgres import controller as controller


def _crash_worker(url, path, secret, trust, private_key, operation, boundary):
    # Disposable fixture credentials travel only in process arguments, never in
    # logs or repository files. No production fault switch is introduced.
    os.environ["WHITEPACT_ENV"] = "staging"

    async def run():
        engine = create_engine(url)
        provider = SqliteDurableLifecycleStateProvider(path, secret_key=secret)

        class InterruptedController(ProtectedTenantController):
            commits = 0

            @asynccontextmanager
            async def transaction(self):
                async with super().transaction() as connection:
                    yield connection
                self.commits += 1
                if boundary == f"commit-{self.commits}":
                    os._exit(91)

        service = InterruptedController(
            engine, provider, trust, Ed25519PrivateKey.from_private_bytes(private_key)
        )
        if boundary == "store-b-published":
            original = service.ledger.publish

            def publish(*args, **kwargs):
                original(*args, **kwargs)
                # Store B is committed; the surrounding PG transaction is not.
                os._exit(91)

            service.ledger.publish = publish
        await service.create(**operation)
        await engine.close()

    asyncio.run(run())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "boundary", ["commit-1", "commit-2", "store-b-published", "commit-3", "commit-4", "commit-5"]
)
async def test_restart_reconciles_only_exact_durable_provisioning_evidence(controller, boundary):
    service, _, _, token, csrf = controller
    operation = dict(
        session_token=token,
        csrf=csrf,
        request_id="abrupt-process-exit",
        name="Crash Qualification",
        slug="crash-qualification",
    )
    process = multiprocessing.get_context("spawn").Process(
        target=_crash_worker,
        args=(
            service.engine.raw.url.render_as_string(hide_password=False),
            service.provider.path,
            service.provider._secret_key,
            service.trust,
            service.key.private_bytes_raw(),
            operation,
            boundary,
        ),
    )
    process.start()
    try:
        await asyncio.to_thread(process.join, 30)
        assert not process.is_alive(), "Provisioning child did not reach its bounded crash point"
        assert process.exitcode == 91
    finally:
        if process.is_alive():
            process.kill()
            await asyncio.to_thread(process.join, 5)
    with sqlite3.connect(service.provider.path) as connection:
        before = connection.execute(
            "SELECT tenant_id,generation_id FROM tenant_provisioning_reservations"
        ).fetchone()
    assert before is not None
    tenant = await service.create(**operation)
    assert tenant == before[0]
    assert service.provider.get_state(tenant).generation_id == before[1]
    assert service.ledger.completion(tenant).generation_id == before[1]
    assert service.provider.get_readiness_state() == RestoreReadinessState.READY
    async with service.engine.raw.connect() as connection:
        assert await connection.scalar(text("SELECT count(*) FROM organizations")) == 1
        assert (
            await connection.scalar(
                text("SELECT count(*) FROM tenant_provisioning_records WHERE state='COMPLETE'")
            )
            == 1
        )
        assert await connection.scalar(text("SELECT count(*) FROM tenant_provisioning_outbox")) == 1
