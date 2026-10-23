# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Explicit fixture identity preservation, not onboarding/controller qualification."""

import secrets

import pytest

from responsibleai.data_governance.backup_defense import (
    LifecycleState,
    LifecycleStateRecord,
    get_restore_readiness_gate,
    set_restore_readiness_gate,
)
from responsibleai.data_governance.deletion_orchestrator import (
    TenantDeletionError,
    TenantDeletionOrchestrator,
)
from responsibleai.db.org_repository import OrgRepository
from tests.test_operator_recovery_postgres import real_recovery as real_recovery


@pytest.mark.asyncio
@pytest.mark.parametrize("real_recovery", ["normal"], indirect=True)
async def test_restrictive_deletion_preserves_established_identity_and_floors(real_recovery):
    engine, provider, gate, _, _ = real_recovery
    previous = get_restore_readiness_gate()
    set_restore_readiness_gate(gate)
    try:
        org = await OrgRepository(engine).create_org("Deletion fixture", secrets.token_hex(8))
        generation = secrets.token_hex(32)
        provider.record_state(
            LifecycleStateRecord(
                tenant_id=org.id,
                generation_id=generation,
                state=LifecycleState.ACTIVE,
                effective_at="2026-10-23T00:00:00+00:00",
                security_epoch=7,
                revocation_floor=6,
            )
        )
        result = await TenantDeletionOrchestrator(engine, provider).delete_tenant(
            org.id, deleted_by="explicit-test-fixture", reason="identity-preservation-regression"
        )
        record = provider.get_state(org.id)
        assert result.generation_id == generation
        assert record.generation_id == generation
        assert record.state == LifecycleState.TOMBSTONED
        assert record.security_epoch == 7
        assert record.revocation_floor == 6
    finally:
        set_restore_readiness_gate(previous)


@pytest.mark.asyncio
@pytest.mark.parametrize("real_recovery", ["normal"], indirect=True)
async def test_unestablished_tenant_deletion_does_not_fabricate_store_b_generation(real_recovery):
    engine, provider, gate, _, _ = real_recovery
    previous = get_restore_readiness_gate()
    set_restore_readiness_gate(gate)
    try:
        org = await OrgRepository(engine).create_org("Unestablished fixture", secrets.token_hex(8))
        with pytest.raises(TenantDeletionError, match="unestablished"):
            await TenantDeletionOrchestrator(engine, provider).delete_tenant(
                org.id, deleted_by="explicit-test-fixture", reason="no-generation-synthesis"
            )
        assert provider.get_state(org.id) is None
        assert await OrgRepository(engine).get_org(org.id) is not None
    finally:
        set_restore_readiness_gate(previous)
