# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""SIEM audit export (P1-06)."""

from __future__ import annotations

import json
import os

os.environ.setdefault("RAI_DB_PATH", ":memory:")
os.environ.setdefault("RAI_AUTH_ENABLED", "false")
os.environ.setdefault("RAI_AUTO_MIGRATE", "true")

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from responsibleai.audit.siem_export import audit_row_to_siem_event, encode_siem_jsonl
from responsibleai.dashboard.app import app


@pytest.fixture()
async def client():
    async with LifespanManager(app, startup_timeout=30) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app),
            base_url="http://test",
            timeout=30.0,
        ) as c:
            yield c


def test_audit_row_to_siem_event_maps_tenant_and_correlation() -> None:
    row = {
        "id": "aud-1",
        "timestamp": "2026-10-02T10:00:00Z",
        "org_id": "org-abc",
        "key_id": "web:user-1",
        "endpoint": "/api/governance/approvals",
        "method": "GET",
        "status_code": 200,
        "request_id": "req-99",
        "duration_ms": 12,
        "entry_hash": "hash-a",
        "prev_hash": "hash-z",
    }
    event = audit_row_to_siem_event(row)
    assert event["tenant_id"] == "org-abc"
    assert event["principal_id"] == "web:user-1"
    assert event["correlation_id"] == "req-99"
    assert event["governance_surface"] is True
    assert event["integrity"]["entry_hash"] == "hash-a"


def test_encode_siem_jsonl_is_ndjson() -> None:
    body = encode_siem_jsonl(
        [
            {
                "org_id": "o1",
                "key_id": "k1",
                "timestamp": "t",
                "endpoint": "/api/health",
                "method": "GET",
                "status_code": 200,
                "request_id": "r1",
            }
        ]
    )
    lines = [line for line in body.strip().split("\n") if line]
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["schema"] == "whitepact.siem.audit.v1"


@pytest.mark.asyncio
async def test_siem_export_endpoint_requires_org_context(client: AsyncClient) -> None:
    r = await client.get("/api/audit/siem-export")
    assert r.status_code == 403
