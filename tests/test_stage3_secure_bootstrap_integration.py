# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Selective Antigravity integration: use the protected Codex publisher.

The positive empty-tenant objective originates in df92a01b. These tests do
not import its alternate publisher or opt historical fixtures out of R1.
"""

from pathlib import Path

import pytest
from scripts.engineering.m13_bootstrap_customer_fixture import authorized_disposable_installation
from scripts.engineering.m13_stage3_customer_fixture import isolated_provisioning_controller
from scripts.engineering.m13i2_customer_journey import isolated_startup_store_b
from sqlalchemy import text

from responsibleai.data_governance.backup_defense import (
    RestoreReadinessGate,
    RestoreReadinessState,
)
from tests.test_stage3_bootstrap_store_preflight import fresh_target as fresh_target


@pytest.mark.asyncio
async def test_signed_customer_bootstrap_publishes_readiness_not_tenant_authority(fresh_target):
    engine, _, _, _ = fresh_target
    with isolated_startup_store_b():
        async with isolated_provisioning_controller(
            engine.raw.url.render_as_string(hide_password=False), authorized_bootstrap=True
        ) as service:
            assert service.provider.get_readiness_state() == RestoreReadinessState.READY
            assert service.provider.verify_integrity()
            assert service.provider.list_all() == []
            assert service.readiness_epoch() >= 1
            async with engine.raw.connect() as connection:
                for table in (
                    "organizations",
                    "governance_execution_nonces",
                    "governance_execution_authorizations",
                ):
                    assert await connection.scalar(text(f"SELECT count(*) FROM {table}")) == 0


@pytest.mark.asyncio
async def test_customer_without_installation_authority_remains_quarantined(fresh_target):
    engine, _, _, _ = fresh_target
    with isolated_startup_store_b():
        async with isolated_provisioning_controller(
            engine.raw.url.render_as_string(hide_password=False)
        ) as service:
            assert service.provider.get_readiness_state() is None
            gate = RestoreReadinessGate(provider=service.provider, db_engine=engine)
            assert gate.state == RestoreReadinessState.RESTORE_PENDING
            assert not gate.is_admitted()
            assert service.provider.list_all() == []


@pytest.mark.asyncio
async def test_lost_external_completion_cannot_leave_admission_ready(fresh_target):
    engine, provider, _, _ = fresh_target
    async with authorized_disposable_installation(
        engine, provider, deployment_id="secure-integration-disposable"
    ):
        gate = RestoreReadinessGate(provider=provider, db_engine=engine)
        assert gate.is_admitted()
        # Fault injection into this disposable fixture only. Preserve Store B,
        # removing the independent receipt rather than manufacturing authority.
        with provider._get_connection() as connection:
            profile_path = connection.execute(
                "SELECT profile_path FROM bootstrap_installation_binding"
            ).fetchone()[0]
        import json

        profile = json.loads(Path(profile_path).read_text())
        authorization = json.loads(Path(profile["authorization_profile"]).read_text())
        Path(authorization["registry"]).unlink()
        assert gate.state == RestoreReadinessState.FAILED
        assert not gate.is_admitted()
        assert provider.list_all() == []
