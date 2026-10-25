# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""FAILED projection cannot attest integrity or authorize corrupt Store B."""

import pytest
from scripts.engineering.m13_bootstrap_authorization import BootstrapStoreIntegrityError
from scripts.engineering.m13_bootstrap_publication import verify_isolated_bootstrap_binding
from sqlalchemy import text

from responsibleai.data_governance.backup_defense import RestoreReadinessState
from responsibleai.data_governance.operator_recovery import RecoveryAuthorizationError
from responsibleai.data_governance.operator_recovery_control import prepare_offline_recovery
from tests.stage3_freshness_setup import provision_freshness_tenant
from tests.test_operator_recovery_postgres import real_recovery as real_recovery


@pytest.mark.asyncio
@pytest.mark.parametrize("real_recovery", ["freshness"], indirect=True)
@pytest.mark.parametrize("persist_failed", [False, True])
async def test_corrupt_lifecycle_never_attests_or_restores_ready(real_recovery, persist_failed):
    engine, provider, gate, profile, _ = real_recovery
    _, tenant, _, _ = await provision_freshness_tenant(engine, provider)
    original = provider.get_state(tenant)
    if persist_failed:
        provider.set_readiness_state(RestoreReadinessState.FAILED)
    # Fault injection is confined to the disposable Store B. Do not replace
    # its identity, the bootstrap receipt or the original generation.
    with provider._get_connection() as connection:
        connection.execute(
            "UPDATE durable_tenant_lifecycle_states SET digest=? WHERE tenant_id=?",
            ("0" * 64, tenant),
        )
    assert not provider.verify_integrity()
    with pytest.raises(BootstrapStoreIntegrityError):
        verify_isolated_bootstrap_binding(provider)
    if persist_failed:
        assert provider.get_readiness_state() == RestoreReadinessState.FAILED
    else:
        with pytest.raises(BootstrapStoreIntegrityError):
            provider.get_readiness_state()
    assert gate.state == RestoreReadinessState.FAILED
    assert not gate.is_admitted()
    with pytest.raises((BootstrapStoreIntegrityError, RecoveryAuthorizationError)):
        provider.set_readiness_state(RestoreReadinessState.READY)
    with pytest.raises(RecoveryAuthorizationError):
        await prepare_offline_recovery(engine, provider, profile_path=profile)
    assert not gate.is_admitted()
    with provider._get_connection() as connection:
        generation, digest = connection.execute(
            "SELECT generation_id,digest FROM durable_tenant_lifecycle_states WHERE tenant_id=?",
            (tenant,),
        ).fetchone()
    assert generation == original.generation_id
    assert digest == "0" * 64
    async with engine.raw.connect() as connection:
        for table in ("governance_execution_authorizations", "runtime_execution_attempts"):
            assert await connection.scalar(text(f"SELECT count(*) FROM {table}")) == 0
