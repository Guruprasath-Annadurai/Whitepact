# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Explicit fixture identity preservation, not onboarding/controller qualification."""

import secrets
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from responsibleai.data_governance.backup_defense import (
    LifecycleState,
    RestoreReadinessGate,
    get_restore_readiness_gate,
    set_restore_readiness_gate,
)
from responsibleai.data_governance.deletion_orchestrator import (
    TenantDeletionError,
    TenantDeletionOrchestrator,
)
from responsibleai.db.org_repository import OrgRepository
from tests.test_stage3_controller_postgres import controller as controller


@pytest.mark.asyncio
async def test_restrictive_deletion_preserves_established_identity_and_floors(controller):
    service, _, _, token, csrf = controller
    engine, provider = service.engine, service.provider
    tenant = await service.create(
        session_token=token,
        csrf=csrf,
        request_id="delete-established",
        name="Deletion fixture",
        slug=secrets.token_hex(8),
    )
    gate = RestoreReadinessGate(provider=provider, db_engine=engine)
    previous = get_restore_readiness_gate()
    set_restore_readiness_gate(gate)
    try:
        established = provider.get_state(tenant)
        generation = established.generation_id
        provider.record_state(replace(established, security_epoch=7, revocation_floor=6, digest=""))
        result = await TenantDeletionOrchestrator(engine, provider).delete_tenant(
            tenant, deleted_by="explicit-test-fixture", reason="identity-preservation-regression"
        )
        record = provider.get_state(tenant)
        assert result.generation_id == generation
        assert record.generation_id == generation
        assert record.state == LifecycleState.TOMBSTONED
        assert record.security_epoch == 7
        assert record.revocation_floor == 6
    finally:
        set_restore_readiness_gate(previous)


@pytest.mark.asyncio
async def test_unestablished_tenant_deletion_does_not_fabricate_store_b_generation(controller):
    service, _, _, _, _ = controller
    engine, provider = service.engine, service.provider
    gate = RestoreReadinessGate(provider=provider, db_engine=engine)
    previous = get_restore_readiness_gate()
    set_restore_readiness_gate(gate)
    try:
        tenant = secrets.token_hex(16)
        # Disposable legacy Store A orphan: explicitly DISABLED, never ACTIVE.
        async with engine.raw.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO organizations(id,name,slug,governance_status,created_at) "
                    "VALUES(:id,'Unestablished fixture',:slug,'DISABLED',:created)"
                ),
                {
                    "id": tenant,
                    "slug": secrets.token_hex(8),
                    "created": datetime.now(UTC).isoformat(),
                },
            )
        with pytest.raises(TenantDeletionError, match="unestablished"):
            await TenantDeletionOrchestrator(engine, provider).delete_tenant(
                tenant, deleted_by="explicit-test-fixture", reason="no-generation-synthesis"
            )
        assert provider.get_state(tenant) is None
        assert await OrgRepository(engine).get_org(tenant) is not None
    finally:
        set_restore_readiness_gate(previous)
