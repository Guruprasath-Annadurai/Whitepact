# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""The browser fixture may enroll only fresh infrastructure, never recover it."""

import pytest
from scripts.engineering.m13_stage3_customer_fixture import isolated_provisioning_controller
from scripts.engineering.m13i2_customer_journey import isolated_startup_store_b
from sqlalchemy import text

from responsibleai.data_governance.backup_defense import RestoreReadinessState
from tests.test_operator_recovery_postgres import real_recovery as real_recovery
from tests.test_stage3_controller_postgres import controller as controller


@pytest.mark.asyncio
@pytest.mark.parametrize("real_recovery", [None, "normal"], indirect=True)
async def test_browser_fixture_never_resets_existing_readiness(real_recovery, monkeypatch):
    engine, provider, _, _, _ = real_recovery
    state = provider.get_readiness_state()
    monkeypatch.setenv("WHITEPACT_STORE_B_PATH", str(provider.path))
    monkeypatch.setenv("WHITEPACT_STORE_B_KEY", provider._secret_key)
    with pytest.raises(RuntimeError, match="cannot be reset"):
        async with isolated_provisioning_controller(
            engine.raw.url.render_as_string(hide_password=False)
        ):
            pytest.fail("Existing readiness was reset")
    assert provider.get_readiness_state() == state
    assert state in (RestoreReadinessState.FAILED, RestoreReadinessState.READY)
    assert provider.list_all() == []


@pytest.mark.asyncio
async def test_fresh_browser_controller_enrollment_never_seeds_tenant_or_ready(controller):
    engine = controller[0].engine
    with isolated_startup_store_b():
        async with isolated_provisioning_controller(
            engine.raw.url.render_as_string(hide_password=False)
        ) as service:
            assert service.provider.get_readiness_state() is None
            assert service.provider.list_all() == []
            async with engine.raw.connect() as connection:
                assert await connection.scalar(text("SELECT count(*) FROM organizations")) == 0
                assert (
                    await connection.scalar(
                        text("SELECT count(*) FROM governance_execution_authorizations")
                    )
                    == 0
                )
