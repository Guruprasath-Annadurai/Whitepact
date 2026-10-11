# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Audit export returns the caller's rows, integrity columns, and no other tenant."""

from __future__ import annotations

import csv
import io
import uuid

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from responsibleai.dashboard import app as app_module
from responsibleai.dashboard.app import app, limiter, settings
from responsibleai.rbac.models import AuditEntry, Role
from tests.org_http_fixtures import seed_org_with_key


def _bearer(raw: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {raw}"}


@pytest.fixture()
async def auth_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", ["bootstrap-test-key"])
    monkeypatch.setattr(settings, "database_url", None)
    monkeypatch.setattr(settings, "db_path", ":memory:")
    monkeypatch.setattr(settings, "auto_migrate", False)
    limiter.reset()
    app_module._auth_failure_limiter._failures.clear()
    async with LifespanManager(app, startup_timeout=20) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as ac:
            yield ac
    app_module._auth_failure_limiter._failures.clear()


@pytest.mark.asyncio
async def test_audit_export_contains_only_the_caller_tenant(auth_client: AsyncClient) -> None:
    org_a, key_a, raw_a = await seed_org_with_key(
        name="Export A",
        slug=f"export-a-{uuid.uuid4().hex[:8]}",
        role=Role.ADMIN,
    )
    org_b, key_b, _raw_b = await seed_org_with_key(
        name="Export B",
        slug=f"export-b-{uuid.uuid4().hex[:8]}",
        role=Role.ADMIN,
    )
    repo = app_module._audit_repo
    assert repo is not None
    await repo.write(
        AuditEntry(
            endpoint="/api/governance/evaluate",
            method="POST",
            org_id=org_a,
            key_id=key_a,
            status_code=200,
            request_id="req-a",
        )
    )
    await repo.write(
        AuditEntry(
            endpoint="/api/governance/secret-b",
            method="POST",
            org_id=org_b,
            key_id=key_b,
            status_code=200,
            request_id="req-b",
        )
    )
    response = await auth_client.get("/api/audit/export", headers=_bearer(raw_a))
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert rows
    assert {row["org_id"] for row in rows} == {org_a}
    assert all(row["entry_hash"] for row in rows)
    assert all(row["prev_hash"] for row in rows)
    assert "secret-b" not in response.text
    assert org_b not in response.text
