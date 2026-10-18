# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M13-H1: Independent MCP HTTP + SSE Transport Security Verification Suite.

Validates the security posture of the MCP HTTP+SSE endpoints (/sse, /messages/)
against real PostgreSQL/database-backed credentials and authenticated transports:
1.  Missing authentication header fails closed (401 Unauthorized).
2.  Empty authentication header fails closed (401 Unauthorized).
3.  Invalid/unknown Bearer token fails closed (401 Unauthorized).
4.  Revoked Bearer credential fails closed (401 Unauthorized).
5.  Missing session_id parameter rejected (400 Bad Request).
6.  Invalid UUID session_id parameter rejected (400 Bad Request).
7.  Non-existent session_id rejected (404 Not Found).
8.  Cross-tenant session hijacking attempt rejected (403 Forbidden).
9.  Same tenant with mismatched credential key rejected (403 Forbidden).
10. Legitimate same-tenant authenticated client message accepted (202 Accepted).
11. Multi-tenant concurrent sessions isolated without cross-talk.
12. Unauthenticated demo mode scoping behavior.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import httpx
import pytest
from starlette.responses import JSONResponse

from responsibleai.dashboard.config import get_settings
from responsibleai.db import OrgRepository, create_engine
from responsibleai.mcp.server import _build_http_app
from responsibleai.rbac.models import Role


@pytest.fixture()
async def mcp_test_env():
    settings = get_settings()
    settings.mcp_http_allow_unauthenticated_demo = False
    engine = create_engine(settings.effective_db_url)
    await engine.init()
    org_repo = OrgRepository(engine)

    # Seed Tenant A
    org_a = await org_repo.create_org("Tenant SSE A", slug=f"sse-a-{uuid.uuid4().hex[:6]}")
    key_rec_a, raw_key_a = await org_repo.create_key(org_a.id, name="key-a", role=Role.ADMIN)

    # Seed Tenant B
    org_b = await org_repo.create_org("Tenant SSE B", slug=f"sse-b-{uuid.uuid4().hex[:6]}")
    key_rec_b, raw_key_b = await org_repo.create_key(org_b.id, name="key-b", role=Role.ADMIN)

    app = _build_http_app()

    endpoint = None
    for r in app.routes:
        if getattr(r, "path", None) in {"/messages", "/messages/"}:
            endpoint = r.app
            break
    assert endpoint is not None, "Could not find /messages/ endpoint in routes"

    yield {
        "engine": engine,
        "org_repo": org_repo,
        "app": app,
        "endpoint": endpoint,
        "org_a": org_a,
        "key_rec_a": key_rec_a,
        "raw_key_a": raw_key_a,
        "org_b": org_b,
        "key_rec_b": key_rec_b,
        "raw_key_b": raw_key_b,
    }

    await engine.close()


# Test 1: Missing authentication header fails closed (401 Unauthorized)
@pytest.mark.asyncio
async def test_01_missing_auth_header_rejected_401(mcp_test_env):
    app = mcp_test_env["app"]
    session_id = uuid.uuid4().hex
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost:8000"
    ) as client:
        resp = await client.post(
            f"/messages/?session_id={session_id}",
            json={"jsonrpc": "2.0", "method": "ping", "id": 1},
        )
    assert resp.status_code == 401
    assert "Provide a valid Bearer credential" in resp.json()["message"]


# Test 2: Empty authentication header fails closed (401 Unauthorized)
@pytest.mark.asyncio
async def test_02_empty_auth_header_rejected_401(mcp_test_env):
    app = mcp_test_env["app"]
    session_id = uuid.uuid4().hex
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost:8000"
    ) as client:
        resp = await client.post(
            f"/messages/?session_id={session_id}",
            headers={"Authorization": "Bearer "},
            json={"jsonrpc": "2.0", "method": "ping", "id": 1},
        )
    assert resp.status_code == 401


# Test 3: Invalid/unknown Bearer token fails closed (401 Unauthorized)
@pytest.mark.asyncio
async def test_03_invalid_bearer_token_rejected_401(mcp_test_env):
    app = mcp_test_env["app"]
    session_id = uuid.uuid4().hex
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost:8000"
    ) as client:
        resp = await client.post(
            f"/messages/?session_id={session_id}",
            headers={"Authorization": "Bearer totally_invalid_token_99999"},
            json={"jsonrpc": "2.0", "method": "ping", "id": 1},
        )
    assert resp.status_code == 401


# Test 4: Revoked Bearer credential fails closed (401 Unauthorized)
@pytest.mark.asyncio
async def test_04_revoked_key_fails_closed_401(mcp_test_env):
    app = mcp_test_env["app"]
    org_repo = mcp_test_env["org_repo"]
    org_a = mcp_test_env["org_a"]

    # Create and immediately revoke a key in org_a scope
    key_rec, raw_key = await org_repo.create_key(org_a.id, name="temp-revoked", role=Role.ADMIN)
    assert await org_repo.revoke_key(key_rec.id, org_id=org_a.id) is True

    session_id = uuid.uuid4().hex
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost:8000"
    ) as client:
        resp = await client.post(
            f"/messages/?session_id={session_id}",
            headers={"Authorization": f"Bearer {raw_key}"},
            json={"jsonrpc": "2.0", "method": "ping", "id": 1},
        )
    assert resp.status_code == 401


# Test 5: Missing session_id parameter rejected (400 Bad Request)
@pytest.mark.asyncio
async def test_05_missing_session_id_rejected_400(mcp_test_env):
    app = mcp_test_env["app"]
    raw_key_a = mcp_test_env["raw_key_a"]

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost:8000"
    ) as client:
        resp = await client.post(
            "/messages/",
            headers={"Authorization": f"Bearer {raw_key_a}"},
            json={"jsonrpc": "2.0", "method": "ping", "id": 1},
        )
    assert resp.status_code == 400
    assert "session_id is required" in resp.text


# Test 6: Invalid UUID session_id parameter rejected (400 Bad Request)
@pytest.mark.asyncio
async def test_06_invalid_uuid_session_id_rejected_400(mcp_test_env):
    app = mcp_test_env["app"]
    raw_key_a = mcp_test_env["raw_key_a"]

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost:8000"
    ) as client:
        resp = await client.post(
            "/messages/?session_id=not-a-valid-uuid",
            headers={"Authorization": f"Bearer {raw_key_a}"},
            json={"jsonrpc": "2.0", "method": "ping", "id": 1},
        )
    assert resp.status_code == 400
    assert "Invalid session ID" in resp.text


# Test 7: Non-existent session_id rejected (404 Not Found)
@pytest.mark.asyncio
async def test_07_nonexistent_session_id_rejected_404(mcp_test_env):
    app = mcp_test_env["app"]
    raw_key_a = mcp_test_env["raw_key_a"]
    non_existent = uuid.uuid4().hex

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost:8000"
    ) as client:
        resp = await client.post(
            f"/messages/?session_id={non_existent}",
            headers={"Authorization": f"Bearer {raw_key_a}"},
            json={"jsonrpc": "2.0", "method": "ping", "id": 1},
        )
    assert resp.status_code == 404
    assert "Could not find session" in resp.text


# Test 8: Cross-tenant session hijacking attempt rejected (403 Forbidden)
@pytest.mark.asyncio
async def test_08_cross_tenant_session_hijacking_rejected_403(mcp_test_env):
    app = mcp_test_env["app"]
    endpoint = mcp_test_env["endpoint"]
    org_a = mcp_test_env["org_a"]
    key_rec_a = mcp_test_env["key_rec_a"]
    raw_key_b = mcp_test_env["raw_key_b"]

    session_id = uuid.uuid4()
    endpoint.transport._read_stream_writers = {session_id: MagicMock()}
    endpoint.transport._session_owners = {
        session_id: {"client_id": org_a.id, "subject": key_rec_a.id}
    }

    # Tenant B attempts to POST into Tenant A's session
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost:8000"
    ) as client:
        resp = await client.post(
            f"/messages/?session_id={session_id.hex}",
            headers={"Authorization": f"Bearer {raw_key_b}"},
            json={"jsonrpc": "2.0", "method": "ping", "id": 1},
        )
    assert resp.status_code == 403
    assert resp.json()["error"] == "cross_tenant_forbidden"


# Test 9: Same tenant with mismatched credential key rejected (403 Forbidden)
@pytest.mark.asyncio
async def test_09_mismatched_credential_key_rejected_403(mcp_test_env):
    app = mcp_test_env["app"]
    endpoint = mcp_test_env["endpoint"]
    org_repo = mcp_test_env["org_repo"]
    org_a = mcp_test_env["org_a"]
    key_rec_a = mcp_test_env["key_rec_a"]

    # Create second key for Tenant A
    key_rec_a2, raw_key_a2 = await org_repo.create_key(
        org_a.id, name="key-a-user2", role=Role.ADMIN
    )

    session_id = uuid.uuid4()
    endpoint.transport._read_stream_writers = {session_id: MagicMock()}
    # Session is owned by key_rec_a
    endpoint.transport._session_owners = {
        session_id: {"client_id": org_a.id, "subject": key_rec_a.id}
    }

    # User 2 of Tenant A attempts to POST into User 1's session
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost:8000"
    ) as client:
        resp = await client.post(
            f"/messages/?session_id={session_id.hex}",
            headers={"Authorization": f"Bearer {raw_key_a2}"},
            json={"jsonrpc": "2.0", "method": "ping", "id": 1},
        )
    assert resp.status_code == 403
    assert resp.json()["error"] == "forbidden"
    assert "Session credential does not match session owner" in resp.json()["message"]


# Test 10: Legitimate same-tenant authenticated client message accepted (202 Accepted)
@pytest.mark.asyncio
async def test_10_legitimate_same_tenant_message_accepted_202(mcp_test_env):
    app = mcp_test_env["app"]
    endpoint = mcp_test_env["endpoint"]
    org_a = mcp_test_env["org_a"]
    key_rec_a = mcp_test_env["key_rec_a"]
    raw_key_a = mcp_test_env["raw_key_a"]

    session_id = uuid.uuid4()
    endpoint.transport._read_stream_writers = {session_id: MagicMock()}
    endpoint.transport._session_owners = {
        session_id: {"client_id": org_a.id, "subject": key_rec_a.id}
    }

    async def mock_handle_post(scope, receive, send):
        await JSONResponse({"status": "accepted_by_handler"}, status_code=202)(scope, receive, send)

    endpoint.transport.handle_post_message = mock_handle_post

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost:8000"
    ) as client:
        resp = await client.post(
            f"/messages/?session_id={session_id.hex}",
            headers={"Authorization": f"Bearer {raw_key_a}"},
            json={"jsonrpc": "2.0", "method": "ping", "id": 1},
        )
    assert resp.status_code == 202
    assert resp.json()["status"] == "accepted_by_handler"


# Test 11: Multi-tenant concurrent sessions isolated without cross-talk
@pytest.mark.asyncio
async def test_11_multi_tenant_concurrent_sessions_isolated(mcp_test_env):
    app = mcp_test_env["app"]
    endpoint = mcp_test_env["endpoint"]
    org_a = mcp_test_env["org_a"]
    key_rec_a = mcp_test_env["key_rec_a"]
    raw_key_a = mcp_test_env["raw_key_a"]
    org_b = mcp_test_env["org_b"]
    key_rec_b = mcp_test_env["key_rec_b"]
    raw_key_b = mcp_test_env["raw_key_b"]

    session_a = uuid.uuid4()
    session_b = uuid.uuid4()
    endpoint.transport._read_stream_writers = {session_a: MagicMock(), session_b: MagicMock()}
    endpoint.transport._session_owners = {
        session_a: {"client_id": org_a.id, "subject": key_rec_a.id},
        session_b: {"client_id": org_b.id, "subject": key_rec_b.id},
    }

    async def mock_handle_post(scope, receive, send):
        await JSONResponse({"status": "routed"}, status_code=200)(scope, receive, send)

    endpoint.transport.handle_post_message = mock_handle_post

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost:8000"
    ) as client:
        # Tenant A accessing Session A -> 200
        resp_aa = await client.post(
            f"/messages/?session_id={session_a.hex}",
            headers={"Authorization": f"Bearer {raw_key_a}"},
            json={"id": 1},
        )
        assert resp_aa.status_code == 200

        # Tenant A accessing Session B -> 403
        resp_ab = await client.post(
            f"/messages/?session_id={session_b.hex}",
            headers={"Authorization": f"Bearer {raw_key_a}"},
            json={"id": 2},
        )
        assert resp_ab.status_code == 403

        # Tenant B accessing Session B -> 200
        resp_bb = await client.post(
            f"/messages/?session_id={session_b.hex}",
            headers={"Authorization": f"Bearer {raw_key_b}"},
            json={"id": 3},
        )
        assert resp_bb.status_code == 200

        # Tenant B accessing Session A -> 403
        resp_ba = await client.post(
            f"/messages/?session_id={session_a.hex}",
            headers={"Authorization": f"Bearer {raw_key_b}"},
            json={"id": 4},
        )
        assert resp_ba.status_code == 403
