# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Current-contract positive journey; original blob 727d78a remains immutable.

Disposable operator signatures, development identity delivery and the explicitly
enabled counter qualify integration only, not production enrollment/containment.
"""

import secrets
import sqlite3
import traceback
from dataclasses import replace

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from scripts.engineering.m13i1_customer_journey import serve
from sdk.python.rai_client.governance import GovernanceRequestError, GovernanceRuntimeClient
from sqlalchemy import text

import responsibleai.dashboard.app as dashboard
from responsibleai.data_governance.backup_defense import (
    LifecycleState,
    RestoreReadinessState,
    get_restore_readiness_gate,
    set_restore_readiness_gate,
)
from responsibleai.data_governance.operator_recovery import RecoveryAuthorizationError
from responsibleai.data_governance.operator_recovery_control import (
    execute_offline_recovery,
    prepare_offline_recovery,
)
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
from responsibleai.enterprise.runtime import get_enterprise_engine
from responsibleai.governance.synthetic_counter import SYNTHETIC_COUNTER_TOOL, snapshot
from tests.stage3_controller_helpers import controller_process
from tests.test_customer_real_approval_journey import _counter, _execute, _resolve
from tests.test_operator_recovery_postgres import real_recovery as real_recovery
from tests.test_operator_recovery_postgres import sign
from tests.test_v1_customer_journey import PURPOSE, _login
from tests.test_v1_exactly_one_effect import ADMIN_EMAIL, _prepare_org


@pytest.mark.asyncio
@pytest.mark.parametrize("real_recovery", ["normal"], indirect=True)
async def test_completed_http_provisioning_signed_recovery_and_one_fresh_sdk_effect(
    real_recovery, monkeypatch, seed_runtime_authority
):
    await _run_journey(real_recovery, monkeypatch, seed_runtime_authority)


@pytest.mark.asyncio
@pytest.mark.parametrize("real_recovery", ["normal"], indirect=True)
@pytest.mark.parametrize(
    "fault", ["missing", "rollback", "corrupt", "generation", "tombstone", "incomplete"]
)
async def test_real_http_tenant_faults_cannot_gain_recovery_or_sdk_effects(
    real_recovery, monkeypatch, seed_runtime_authority, fault
):
    await _run_journey(real_recovery, monkeypatch, seed_runtime_authority, fault=fault)


async def _run_journey(real_recovery, monkeypatch, seed_runtime_authority, fault=None):
    engine, provider, gate, profile_path, operators = real_recovery
    # No tenant authority exists yet. Enroll only disposable test controller
    # trust; never reconstruct a generation from an existing organization.
    assert provider.list_all() == []
    provider._secret_key = secrets.token_hex(32)
    key = Ed25519PrivateKey.generate()
    async with engine.raw.connect() as connection:
        pg_identity = await postgres_identity(connection)
    trust = ProvisionerTrust(
        "isolated-sdk-controller",
        key.public_key().public_bytes_raw(),
        "isolated-sdk-provisioning",
        "staging",
        pg_identity,
        store_b_identity(provider),
    )
    PendingTenantReservations(provider).initialize()
    PublicationAuthorizationLedger(provider).initialize(trust)
    service = ProtectedTenantController(engine, provider, trust, key)
    previous = get_restore_readiness_gate()
    set_restore_readiness_gate(gate)
    monkeypatch.setenv("WHITEPACT_STORE_B_PATH", str(provider.path))
    monkeypatch.setenv("WHITEPACT_STORE_B_KEY", provider._secret_key)
    monkeypatch.setenv("WHITEPACT_ALLOW_SYNTHETIC_HOST_TOOL", "1")
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
    monkeypatch.setattr(dashboard.limiter, "enabled", False)
    sanitized_errors = []

    async def observed_app(scope, receive, send):
        try:
            await dashboard.app(scope, receive, send)
        except Exception as exc:
            sanitized_errors.append(
                (
                    type(exc).__name__,
                    [
                        (frame.name, frame.lineno)
                        for frame in traceback.extract_tb(exc.__traceback__)[-8:]
                    ],
                )
            )
            raise

    try:
        async with controller_process(service, monkeypatch):
            async with serve(observed_app) as origin:
                async with httpx.AsyncClient(base_url=origin, timeout=30) as browser:
                    # Real SQLite backup before onboarding: restoring it later
                    # models rollback, not a supported lifecycle mutation.
                    rollback = sqlite3.connect(":memory:")
                    with provider._get_connection() as source:
                        source.backup(rollback)
                    tenant, api_key = await _prepare_org(
                        browser,
                        monkeypatch,
                        seed_runtime_authority,
                        engine.raw.url.render_as_string(hide_password=False),
                    )
                    assert service.ledger.completion(tenant) is not None
                    sdk = GovernanceRuntimeClient(api_key, base_url=origin, timeout=30)
                    assert await _counter(browser, api_key) == 0
                    if fault is not None:
                        await _inject_disposable_fault(service, tenant, fault, rollback)
                    rollback.close()
                    gate.set_state(RestoreReadinessState.FAILED)
                    with pytest.raises(GovernanceRequestError) as denied:
                        await sdk.call_tool(SYNTHETIC_COUNTER_TOOL, purpose=PURPOSE)
                    assert denied.value.status_code == 503
                    live = get_enterprise_engine()
                    if fault is not None:
                        try:
                            rejected_manifest = await prepare_offline_recovery(
                                live, provider, profile_path=profile_path
                            )
                        except RecoveryAuthorizationError:
                            pass
                        else:
                            # Preparation is read-only; even a valid plan for a
                            # tombstoned tenant cannot replace operator approval.
                            with pytest.raises(RecoveryAuthorizationError):
                                await execute_offline_recovery(
                                    live,
                                    provider,
                                    gate,
                                    profile_path=profile_path,
                                    manifest=rejected_manifest,
                                    signatures=[],
                                )
                        with pytest.raises(GovernanceRequestError) as still_denied:
                            await sdk.call_tool(SYNTHETIC_COUNTER_TOOL, purpose=PURPOSE)
                        assert still_denied.value.status_code == 503
                        assert provider.get_readiness_state() == RestoreReadinessState.FAILED
                        async with engine.raw.connect() as connection:
                            assert (
                                await connection.scalar(
                                    text(
                                        "SELECT count(*) FROM governance_execution_nonces WHERE organization_id=:tenant"
                                    ),
                                    {"tenant": tenant},
                                )
                                == 0
                            )
                            assert (
                                await connection.scalar(
                                    text(
                                        "SELECT count(*) FROM governance_execution_authorizations WHERE organization_id=:tenant"
                                    ),
                                    {"tenant": tenant},
                                )
                                == 0
                            )
                        assert await snapshot(tenant) == {"counter": 0, "downstream_call_count": 0}
                        return
                    manifest = await prepare_offline_recovery(
                        live, provider, profile_path=profile_path
                    )
                    await execute_offline_recovery(
                        live,
                        provider,
                        gate,
                        profile_path=profile_path,
                        manifest=manifest,
                        signatures=sign(manifest, operators),
                    )
                    assert provider.get_readiness_state() == RestoreReadinessState.READY
                    assert await _counter(browser, api_key) == 0
                    fresh = await sdk.call_tool(SYNTHETIC_COUNTER_TOOL, purpose=PURPOSE)
                    assert fresh.requires_approval and not fresh.completed
                    assert fresh.approval_id
                    assert await _counter(browser, api_key) == 0
                    first = await _resolve(browser, fresh.approval_id, "APPROVED")
                    assert first.status_code == 200 and first.json()["status"] == "PENDING"
                    assert (await _execute(browser, fresh.approval_id)).status_code == 409
                    logout = await browser.post(
                        "/api/v1/web/auth/logout",
                        headers={"X-WP-CSRF": browser.cookies["wp_csrf"]},
                    )
                    assert logout.status_code == 200
                    await _login(browser, ADMIN_EMAIL)
                    second = await _resolve(browser, fresh.approval_id, "APPROVED")
                    assert second.status_code == 200 and second.json()["status"] == "APPROVED"
                    execution = await _execute(browser, fresh.approval_id)
                    assert execution.status_code == 200, sanitized_errors
                    assert execution.json()["execution_status"] == "SUCCEEDED"
                    assert await _counter(browser, api_key) == 1
                    assert (await _execute(browser, fresh.approval_id)).status_code == 409
                    assert await _counter(browser, api_key) == 1
    finally:
        set_restore_readiness_gate(previous)


async def _inject_disposable_fault(service, tenant, fault, rollback):
    """Administrative corruption of disposable stores only; never production API."""
    if fault == "tombstone":
        record = service.provider.get_state(tenant)
        service.provider.record_state(replace(record, state=LifecycleState.TOMBSTONED, digest=""))
        return
    if fault == "generation":
        async with service.engine.raw.begin() as connection:
            await connection.execute(text("SET LOCAL session_replication_role=replica"))
            await connection.execute(
                text(
                    "UPDATE tenant_provisioning_records SET generation_id=:generation WHERE tenant_id=:tenant"
                ),
                {"generation": secrets.token_hex(32), "tenant": tenant},
            )
        return
    connection = service.provider._get_connection()
    try:
        if fault == "rollback":
            rollback.backup(connection)
        elif fault == "missing":
            connection.execute(
                "DELETE FROM durable_tenant_lifecycle_states WHERE tenant_id=?", (tenant,)
            )
        elif fault == "corrupt":
            connection.execute(
                "UPDATE durable_tenant_lifecycle_states SET digest=? WHERE tenant_id=?",
                ("0" * 64, tenant),
            )
        elif fault == "incomplete":
            connection.execute("DROP TRIGGER tenant_provisioning_completions_no_delete")
            connection.execute(
                "DELETE FROM tenant_provisioning_completions WHERE tenant_id=?", (tenant,)
            )
        else:
            raise AssertionError("Unrecognized disposable fault")
        connection.commit()
    finally:
        connection.close()
