# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Fail closed when genuine onboarding lacks authoritative Store B lifecycle.

This qualifies the recovery/SDK integration, not production customer identity,
operator enrollment or physical Docker effect containment. The counter is the
existing explicitly enabled host-side test tool; no production tool is enabled.
"""

import httpx
import pytest
from scripts.engineering.m13i1_customer_journey import serve
from sdk.python.rai_client.governance import GovernanceRequestError, GovernanceRuntimeClient
from sqlalchemy import func, select

import responsibleai.dashboard.app as dashboard
from responsibleai.data_governance.backup_defense import (
    RestoreReadinessState,
    RestoreReconciliationError,
    get_restore_readiness_gate,
    set_restore_readiness_gate,
)
from responsibleai.data_governance.operator_recovery_control import (
    execute_offline_recovery,
    prepare_offline_recovery,
)
from responsibleai.db.engine import governance_execution_authorizations
from responsibleai.enterprise.runtime import get_enterprise_engine
from responsibleai.governance.synthetic_counter import SYNTHETIC_COUNTER_TOOL
from responsibleai.governance.synthetic_counter import snapshot as counter_snapshot
from tests.test_customer_real_approval_journey import _counter
from tests.test_operator_recovery_postgres import real_recovery as real_recovery
from tests.test_operator_recovery_postgres import sign
from tests.test_v1_customer_journey import PURPOSE
from tests.test_v1_exactly_one_effect import _prepare_org


@pytest.mark.asyncio
@pytest.mark.parametrize("real_recovery", ["normal"], indirect=True)
async def test_customer_missing_authoritative_lifecycle_cannot_recover_through_signatures(
    real_recovery, monkeypatch, seed_runtime_authority
):
    engine, provider, gate, profile_path, private = real_recovery
    monkeypatch.setenv("WHITEPACT_STORE_B_PATH", str(provider.path))
    monkeypatch.setenv("WHITEPACT_ALLOW_SYNTHETIC_HOST_TOOL", "1")
    previous = get_restore_readiness_gate()
    set_restore_readiness_gate(gate)
    for name, value in {
        "database_url": engine.raw.url.render_as_string(hide_password=False),
        "auto_migrate": False,
        "auth_enabled": True,
        "api_keys": [],
        "web_auth_dev_tokens": True,
        "web_session_secure": False,
        "web_verification_delivery_url": None,
        "environment": "development",
    }.items():
        monkeypatch.setattr(dashboard.settings, name, value)
    try:
        async with serve(dashboard.app) as origin:
            async with httpx.AsyncClient(base_url=origin, timeout=30) as browser:
                org_id, key = await _prepare_org(
                    browser,
                    monkeypatch,
                    seed_runtime_authority,
                    engine.raw.url.render_as_string(hide_password=False),
                )
                sdk = GovernanceRuntimeClient(key, base_url=origin, timeout=30)
                assert await _counter(browser, key) == 0
                # Preserve the product gap, not a synthetic ACTIVE record.
                assert provider.get_state(org_id) is None
                gate.set_state(RestoreReadinessState.FAILED)
                with pytest.raises(GovernanceRequestError) as denied:
                    await sdk.call_tool(SYNTHETIC_COUNTER_TOOL, purpose=PURPOSE)
                assert denied.value.status_code == 503
                live_engine = get_enterprise_engine()
                manifest = await prepare_offline_recovery(
                    live_engine, provider, profile_path=profile_path
                )
                with pytest.raises(
                    RestoreReconciliationError, match="lacking authoritative Store B lifecycle"
                ):
                    await execute_offline_recovery(
                        live_engine,
                        provider,
                        gate,
                        profile_path=profile_path,
                        manifest=manifest,
                        signatures=sign(manifest, private),
                    )
                assert gate.state == RestoreReadinessState.FAILED
                assert provider.get_state(org_id) is None
                with pytest.raises(GovernanceRequestError) as still_denied:
                    await sdk.call_tool(SYNTHETIC_COUNTER_TOOL, purpose=PURPOSE)
                assert still_denied.value.status_code == 503
                async with live_engine.raw.connect() as connection:
                    assert (
                        await connection.scalar(
                            select(func.count()).select_from(governance_execution_authorizations)
                        )
                        == 0
                    )
                assert await counter_snapshot(org_id) == {
                    "counter": 0,
                    "downstream_call_count": 0,
                }
    finally:
        set_restore_readiness_gate(previous)
