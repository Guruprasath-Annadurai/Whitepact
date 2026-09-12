# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Multi-tenant Isolation and Security Invariants for WhitePact Phase 5."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import insert, select

from responsibleai.data_governance.deletion_orchestrator import TenantDeletionOrchestrator
from responsibleai.data_governance.export import DataExportService
from responsibleai.data_governance.legal_hold import LegalHoldManager
from responsibleai.data_governance.retention import RetentionManager
from responsibleai.db.engine import (
    DatabaseEngine,
    create_engine,
    eval_runs,
    incidents,
    organizations,
)
from responsibleai.governance.models import GovernanceDecision
from responsibleai.governance.policy import PolicyRule
from responsibleai.governance.policy_lifecycle import (
    PolicyLifecycleManager,
    PolicyRevisionNotFoundError,
)


@pytest.fixture
async def sqlite_engine():
    engine = create_engine(":memory:")
    await engine.init()
    yield engine
    await engine.close()


@pytest.fixture
async def tenant_pair(sqlite_engine: DatabaseEngine):
    tenant_a = f"tenant-a-{uuid.uuid4().hex[:6]}"
    tenant_b = f"tenant-b-{uuid.uuid4().hex[:6]}"
    async with sqlite_engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id=tenant_a,
                name="Tenant Alpha Corp",
                slug=f"slug-{uuid.uuid4().hex[:6]}",
                created_at="2026-09-12T00:00:00Z",
            )
        )
        await conn.execute(
            insert(organizations).values(
                id=tenant_b,
                name="Tenant Beta Corp",
                slug=f"slug-{uuid.uuid4().hex[:6]}",
                created_at="2026-09-12T00:00:00Z",
            )
        )
    return tenant_a, tenant_b


@pytest.mark.asyncio
async def test_policy_lifecycle_tenant_isolation(sqlite_engine: DatabaseEngine, tenant_pair: tuple[str, str]):
    tenant_a, tenant_b = tenant_pair
    mgr = PolicyLifecycleManager(sqlite_engine)

    # 1. Draft policy for tenant A
    rules_a = [PolicyRule(rule_id="r1", reason_code="RC_ALLOW", effect=GovernanceDecision.ALLOW)]
    rev_a = await mgr.create_revision(
        org_id=tenant_a,
        rules=rules_a,
        created_by="user-a",
        change_reason="Tenant A initial rules",
    )

    # 2. Verify tenant B cannot activate tenant A's revision
    with pytest.raises(PolicyRevisionNotFoundError, match="not found"):
        await mgr.activate_revision(
            org_id=tenant_b,
            revision_id=rev_a.id,
            activated_by="user-b",
        )

    # 3. Activate for tenant A
    act_a = await mgr.activate_revision(
        org_id=tenant_a,
        revision_id=rev_a.id,
        activated_by="user-a",
    )
    assert act_a.org_id == tenant_a

    # 4. Verify tenant B's active policy remains None
    active_b = await mgr.get_active_activation(tenant_b)
    assert active_b is None


@pytest.mark.asyncio
async def test_data_export_tenant_isolation(sqlite_engine: DatabaseEngine, tenant_pair: tuple[str, str]):
    tenant_a, tenant_b = tenant_pair
    export_svc = DataExportService(sqlite_engine)

    # Seed records for both tenants
    async with sqlite_engine.raw.begin() as conn:
        await conn.execute(
            insert(incidents).values(
                id=str(uuid.uuid4()),
                org_id=tenant_a,
                incident_type="SECURITY",
                severity="HIGH",
                siem_event_type="ALERT",
                description="Incident A Only",
                evidence_hash="hash-a-1",
                status="OPEN",
                created_at="2026-09-12T00:00:00Z",
            )
        )
        await conn.execute(
            insert(incidents).values(
                id=str(uuid.uuid4()),
                org_id=tenant_b,
                incident_type="SECURITY",
                severity="HIGH",
                siem_event_type="ALERT",
                description="Incident B Only",
                evidence_hash="hash-b-1",
                status="OPEN",
                created_at="2026-09-12T00:00:00Z",
            )
        )

    # Tenant A export
    export_bundle_a = await export_svc.export_tenant_data(tenant_a, requested_by="user-a")

    assert export_bundle_a.manifest.org_id == tenant_a
    incidents_a = export_bundle_a.data.get("incidents", [])
    assert len(incidents_a) == 1
    assert incidents_a[0]["description"] == "Incident A Only"
    assert incidents_a[0]["org_id"] == tenant_a

    # Verify no tenant B data leaked into Tenant A's export bundle
    for _table_name, rows in export_bundle_a.data.items():
        for row in rows:
            if "org_id" in row:
                assert row["org_id"] == tenant_a
            if "organization_id" in row:
                assert row["organization_id"] == tenant_a


@pytest.mark.asyncio
async def test_legal_hold_and_retention_tenant_isolation(sqlite_engine: DatabaseEngine, tenant_pair: tuple[str, str]):
    tenant_a, tenant_b = tenant_pair
    hold_mgr = LegalHoldManager(sqlite_engine)
    ret_mgr = RetentionManager(sqlite_engine)

    # 1. Place legal hold strictly on Tenant A
    await hold_mgr.create_hold(
        org_id=tenant_a,
        data_category="TENANT_OPERATIONAL",
        hold_reason="Litigation A",
        created_by="legal-counsel-a",
    )

    # 2. Check hold status
    assert await hold_mgr.is_held(tenant_a, "TENANT_OPERATIONAL") is True
    assert await hold_mgr.is_held(tenant_b, "TENANT_OPERATIONAL") is False

    # 3. Configure retention policy for both
    await ret_mgr.set_retention_policy(tenant_a, "TENANT_OPERATIONAL", 30 * 86400)
    await ret_mgr.set_retention_policy(tenant_b, "TENANT_OPERATIONAL", 30 * 86400)

    # Seed data older than 30 days for both tenants
    async with sqlite_engine.raw.begin() as conn:
        await conn.execute(
            insert(eval_runs).values(
                id=str(uuid.uuid4()),
                org_id=tenant_a,
                run_type="benchmark",
                model="gpt-4",
                provider="openai",
                payload="{}",
                created_at="2026-08-01T00:00:00Z",
            )
        )
        await conn.execute(
            insert(eval_runs).values(
                id=str(uuid.uuid4()),
                org_id=tenant_b,
                run_type="benchmark",
                model="gpt-4",
                provider="openai",
                payload="{}",
                created_at="2026-08-01T00:00:00Z",
            )
        )

    # 4. Pruning tenant A is blocked by hold
    report_a = await ret_mgr.run_retention_cleanup(tenant_a)
    assert len(report_a.held_categories) == 1
    assert "eval_runs" not in report_a.pruned_records

    # 5. Pruning tenant B is NOT blocked by tenant A's hold
    report_b = await ret_mgr.run_retention_cleanup(tenant_b)
    assert len(report_b.held_categories) == 0
    assert report_b.pruned_records.get("eval_runs", 0) == 1


@pytest.mark.asyncio
async def test_tenant_deletion_isolation(sqlite_engine: DatabaseEngine, tenant_pair: tuple[str, str]):
    tenant_a, tenant_b = tenant_pair
    orchestrator = TenantDeletionOrchestrator(sqlite_engine)

    # Seed data for both tenants
    async with sqlite_engine.raw.begin() as conn:
        await conn.execute(
            insert(incidents).values(
                id=str(uuid.uuid4()),
                org_id=tenant_a,
                incident_type="OPS",
                severity="LOW",
                siem_event_type="ALERT",
                description="Incident A",
                evidence_hash="hash-del-a",
                status="CLOSED",
                created_at="2026-09-12T00:00:00Z",
            )
        )
        await conn.execute(
            insert(incidents).values(
                id=str(uuid.uuid4()),
                org_id=tenant_b,
                incident_type="OPS",
                severity="LOW",
                siem_event_type="ALERT",
                description="Incident B",
                evidence_hash="hash-del-b",
                status="OPEN",
                created_at="2026-09-12T00:00:00Z",
            )
        )

    # Execute deletion of Tenant A
    result_a = await orchestrator.delete_tenant(
        org_id=tenant_a,
        deleted_by="dpo-admin",
        reason="Customer termination A",
    )
    assert result_a.verification_passed is True

    # Verify Tenant B is completely untouched and intact
    async with sqlite_engine.raw.connect() as conn:
        org_b = (
            await conn.execute(select(organizations).where(organizations.c.id == tenant_b))
        ).fetchone()
        assert org_b is not None
        assert org_b.name == "Tenant Beta Corp"

        incidents_b = (
            await conn.execute(select(incidents).where(incidents.c.org_id == tenant_b))
        ).fetchall()
        assert len(incidents_b) == 1
        assert incidents_b[0].description == "Incident B"
