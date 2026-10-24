# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tests for Phase 5 Tenant Deletion Orchestration & Generational Tombstoning."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import insert, select

from responsibleai.data_governance.backup_defense import (
    LifecycleState,
    RestoreReadinessGate,
    get_restore_readiness_gate,
    set_restore_readiness_gate,
)
from responsibleai.data_governance.deletion_orchestrator import (
    TenantDeletionOrchestrator,
)
from responsibleai.data_governance.legal_hold import LegalHoldActiveError, LegalHoldManager
from responsibleai.db.engine import (
    DatabaseEngine,
    create_engine,
    incidents,
    org_api_keys,
    organizations,
    tenant_tombstones,
    web_sessions,
    web_users,
)
from tests.test_stage3_controller_postgres import controller as controller


@pytest.fixture
async def sqlite_engine():
    engine = create_engine(":memory:")
    await engine.init()
    yield engine
    await engine.close()


@pytest.fixture
async def sample_org(sqlite_engine: DatabaseEngine):
    org_id = f"org-{uuid.uuid4().hex[:8]}"
    async with sqlite_engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id=org_id,
                name="Test Org Deletion",
                slug=f"slug-{uuid.uuid4().hex[:8]}",
                created_at="2026-09-12T00:00:00Z",
            )
        )
    return org_id


@pytest.mark.asyncio
@pytest.mark.parametrize("protected_tenant", ["postgresql16"], indirect=True)
async def test_end_to_end_tenant_deletion(protected_tenant):
    service, sample_org, generation = protected_tenant
    sqlite_engine = service.engine  # Historical variable, now a real PostgreSQL transport.
    orchestrator = TenantDeletionOrchestrator(sqlite_engine, lifecycle_provider=service.provider)

    # Populate active tenant resources
    async with sqlite_engine.raw.begin() as conn:
        # User & Session
        user_id = str(uuid.uuid4())
        await conn.execute(
            insert(web_users).values(
                id=user_id,
                email=f"user-{user_id[:8]}@example.com",
                full_name="Test User",
                password_hash="secret-hash",
                created_at="2026-09-12T00:00:00Z",
                updated_at="2026-09-12T00:00:00Z",
            )
        )
        await conn.execute(
            insert(web_sessions).values(
                token_hash="hash-sess",
                user_id=user_id,
                org_id=sample_org,
                csrf_hash="csrf-hash-123",
                expires_at="2026-09-20T00:00:00Z",
                created_at="2026-09-12T00:00:00Z",
                last_seen_at="2026-09-12T00:00:00Z",
                revoked=0,
            )
        )
        # API Key
        await conn.execute(
            insert(org_api_keys).values(
                id=str(uuid.uuid4()),
                org_id=sample_org,
                key_hash="hash-key-123",
                name="Test Key",
                role="ADMIN",
                created_at="2026-09-12T00:00:00Z",
                revoked=0,
            )
        )
        # Incident
        await conn.execute(
            insert(incidents).values(
                id=str(uuid.uuid4()),
                org_id=sample_org,
                incident_type="SYSTEM",
                severity="LOW",
                siem_event_type="ALERT",
                description="Ops incident",
                evidence_hash="hash-44",
                status="OPEN",
                created_at="2026-09-12T00:00:00Z",
            )
        )

    # Execute deletion
    result = await orchestrator.delete_tenant(
        sample_org, "root-admin", "Customer requested departure"
    )

    assert result.verification_passed is True
    assert result.generation_id == generation
    final = service.provider.get_state(sample_org)
    assert final.state == LifecycleState.TOMBSTONED
    assert final.generation_id == generation

    # Verify sessions and API keys are completely deleted
    async with sqlite_engine.raw.connect() as conn:
        s_count = (
            await conn.execute(select(web_sessions).where(web_sessions.c.org_id == sample_org))
        ).fetchall()
        assert len(s_count) == 0

        k_count = (
            await conn.execute(select(org_api_keys).where(org_api_keys.c.org_id == sample_org))
        ).fetchall()
        assert len(k_count) == 0

        # Verify durable tombstone exists
        tombstone = (
            await conn.execute(
                select(tenant_tombstones).where(tenant_tombstones.c.org_id == sample_org)
            )
        ).fetchone()
        assert tombstone is not None
        assert tombstone.generation_id == result.generation_id
        assert tombstone.generation_id == generation
        assert tombstone.tombstoned_by == "root-admin"


@pytest.fixture
async def protected_tenant(controller):
    service, _, _, token, csrf = controller
    previous = get_restore_readiness_gate()
    set_restore_readiness_gate(
        RestoreReadinessGate(provider=service.provider, db_engine=service.engine)
    )
    try:
        tenant = await service.create(
            session_token=token,
            csrf=csrf,
            request_id="historical-deletion-provisioning",
            name="Test Org Deletion",
            slug="historical-deletion-provisioned",
        )
        established = service.provider.get_state(tenant)
        assert established.state == LifecycleState.ACTIVE
        completion = service.ledger.completion(tenant)
        assert completion.generation_id == established.generation_id
        async with service.engine.raw.connect() as connection:
            from sqlalchemy import text

            row = (
                (
                    await connection.execute(
                        text(
                            "SELECT generation_id,state,completion_digest FROM tenant_provisioning_records "
                            "WHERE tenant_id=:tenant"
                        ),
                        {"tenant": tenant},
                    )
                )
                .mappings()
                .one()
            )
            assert row["generation_id"] == established.generation_id
            assert row["state"] == "COMPLETE"
            assert row["completion_digest"] == completion.completion_digest
        yield service, tenant, established.generation_id
    finally:
        set_restore_readiness_gate(previous)


@pytest.mark.asyncio
async def test_tenant_deletion_blocked_by_legal_hold(
    sqlite_engine: DatabaseEngine, sample_org: str
):
    orchestrator = TenantDeletionOrchestrator(sqlite_engine)
    hold_mgr = LegalHoldManager(sqlite_engine)

    # Place hold
    await hold_mgr.create_hold(sample_org, "ALL", "Court order", "counsel")

    # Deletion MUST fail closed with LegalHoldActiveError
    with pytest.raises(LegalHoldActiveError):
        await orchestrator.delete_tenant(sample_org, "admin", "Attempted delete under hold")
