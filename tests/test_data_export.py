# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tests for Phase 5 Structured Data Export & Zero-Secret Isolation."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import insert

from responsibleai.data_governance.export import DataExportService
from responsibleai.db.engine import (
    DatabaseEngine,
    create_engine,
    governance_crypto_keys,
    incidents,
    organizations,
)


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
                name="Test Org Export",
                slug=f"slug-{uuid.uuid4().hex[:8]}",
                created_at="2026-09-12T00:00:00Z",
            )
        )
    return org_id


@pytest.mark.asyncio
async def test_structured_export_with_manifest_and_zero_secrets(sqlite_engine: DatabaseEngine, sample_org: str):
    export_svc = DataExportService(sqlite_engine)

    # Insert operational data
    async with sqlite_engine.raw.begin() as conn:
        await conn.execute(
            insert(incidents).values(
                id=str(uuid.uuid4()),
                org_id=sample_org,
                incident_type="SECURITY",
                severity="HIGH",
                siem_event_type="ALERT",
                description="Security Alert Description",
                evidence_hash="ev-hash-1",
                status="OPEN",
                created_at="2026-09-12T00:00:00Z",
            )
        )
        # Insert a secret crypto key
        await conn.execute(
            insert(governance_crypto_keys).values(
                key_id="key-123",
                tenant_id=sample_org,
                purpose="FIELD_ENCRYPTION",
                environment="test",
                version=1,
                wrapped_dek="wrapped-secret-dek",
                status="active",
                created_at="2026-09-12T00:00:00Z",
            )
        )

    # Perform export
    bundle = await export_svc.export_tenant_data(sample_org, "admin-exporter")

    # Verify manifest
    assert bundle.manifest.org_id == sample_org
    assert bundle.manifest.requested_by == "admin-exporter"
    assert bundle.manifest.integrity_digest is not None
    assert len(bundle.manifest.integrity_digest) == 64

    # Verify incidents are present
    assert "incidents" in bundle.data
    assert len(bundle.data["incidents"]) == 1
    assert bundle.data["incidents"][0]["description"] == "Security Alert Description"

    # Invariant: ZERO-SECRET EXPORT. Crypto keys must NEVER appear in export data!
    assert "governance_crypto_keys" not in bundle.data


@pytest.mark.asyncio
async def test_cross_tenant_export_isolation(sqlite_engine: DatabaseEngine, sample_org: str):
    export_svc = DataExportService(sqlite_engine)
    other_org = f"org-other-{uuid.uuid4().hex[:8]}"

    async with sqlite_engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id=other_org,
                name="Other Org",
                slug=f"slug-{uuid.uuid4().hex[:8]}",
                created_at="2026-09-12T00:00:00Z",
            )
        )
        await conn.execute(
            insert(incidents).values(
                id=str(uuid.uuid4()),
                org_id=other_org,
                incident_type="SECURITY",
                severity="LOW",
                siem_event_type="ALERT",
                description="Other Org Incident Description",
                evidence_hash="ev-hash-2",
                status="RESOLVED",
                created_at="2026-09-12T00:00:00Z",
            )
        )

    bundle = await export_svc.export_tenant_data(sample_org, "admin")
    assert len(bundle.data.get("incidents", [])) == 0
