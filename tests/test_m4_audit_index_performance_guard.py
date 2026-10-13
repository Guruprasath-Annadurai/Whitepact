# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M4 audit tenant-filter performance guard (realistic dataset, bounded query)."""

from __future__ import annotations

import time
import uuid

import pytest

from responsibleai.db.audit_repository import AuditRepository
from responsibleai.db.engine import create_engine
from responsibleai.rbac.models import AuditEntry


@pytest.fixture
async def audit_engine():
    db = create_engine(":memory:")
    await db.init()
    yield db
    await db.close()


@pytest.mark.asyncio
async def test_tenant_filtered_audit_query_bounded_and_isolated(audit_engine) -> None:
    repo = AuditRepository(audit_engine)
    for i in range(400):
        org = "org-alpha" if i % 2 == 0 else "org-beta"
        await repo.write(
            AuditEntry(
                id=str(uuid.uuid4()),
                org_id=org,
                key_id="key-1",
                endpoint="/api/governance/evaluate",
                method="POST",
                status_code=200,
            )
        )

    start = time.perf_counter()
    rows = await repo.query(org_id="org-alpha", days=30, limit=50)
    elapsed = time.perf_counter() - start

    assert len(rows) == 50
    assert all(r["org_id"] == "org-alpha" for r in rows)
    assert elapsed < 0.5, f"tenant-filtered audit query too slow: {elapsed:.3f}s"
