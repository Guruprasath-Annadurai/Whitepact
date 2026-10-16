# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Adversarial security qualification for MCP SSE transport (/messages/ endpoint).

Tests session binding, tenant isolation, authentication enforcement,
and anti-hijacking protections on the MCP HTTP+SSE transport.
"""

from __future__ import annotations

import uuid

import anyio
import httpx
import pytest
from asgi_lifespan import LifespanManager

import responsibleai.db as db_module
from responsibleai.db import OrgRepository, create_engine
from responsibleai.mcp.server import _build_http_app
from responsibleai.rbac.models import Plan, Role


@pytest.fixture()
async def dual_tenant_app(monkeypatch: pytest.MonkeyPatch):
    """Fixture providing a real hosted MCP app with two distinct organizations."""
    engine = create_engine(":memory:")
    await engine.init()
    monkeypatch.setattr(db_module, "create_engine", lambda _url: engine)

    org_repo = OrgRepository(engine)
    org_a = await org_repo.create_org("Tenant Alpha", "tenant-alpha", plan=Plan.ENTERPRISE)
    key_rec_a, key_a = await org_repo.create_key(org_a.id, "key-alpha-admin", role=Role.ADMIN)
    key_rec_a_analyst, key_a_analyst = await org_repo.create_key(
        org_a.id, "key-alpha-analyst", role=Role.ANALYST
    )

    org_b = await org_repo.create_org("Tenant Beta", "tenant-beta", plan=Plan.ENTERPRISE)
    key_rec_b, key_b = await org_repo.create_key(org_b.id, "key-beta-admin", role=Role.ADMIN)

    app = _build_http_app()
    transport = _get_sse_transport(app)
    async with LifespanManager(app) as manager:
        yield (
            manager.app,
            {
                "transport": transport,
                "org_a": org_a,
                "key_a": key_a,
                "key_id_a": key_rec_a.id,
                "key_a_analyst": key_a_analyst,
                "key_id_a_analyst": key_rec_a_analyst.id,
                "org_b": org_b,
                "key_b": key_b,
                "key_id_b": key_rec_b.id,
            },
        )


def _get_sse_transport(app):
    """Extract the bound SseServerTransport instance from the Starlette app."""
    for route in app.routes:
        if getattr(route, "path", "") == "/messages":
            target = route.app
            if hasattr(target, "__self__"):
                return target.__self__
            elif hasattr(target, "transport"):
                return target.transport
    raise RuntimeError("Could not find /messages route on app")


class TestMcpSseTransportAdversarial:
    async def test_unauthenticated_post_messages_is_rejected_with_401(
        self, dual_tenant_app
    ) -> None:
        """An unauthenticated POST to /messages/ must be rejected with 401 Unauthorized,
        regardless of whether the targeted session exists or not.
        """
        app, creds = dual_tenant_app
        transport = creds["transport"]

        session_id = uuid.uuid4()
        writer, _reader = anyio.create_memory_object_stream(10)
        transport._read_stream_writers[session_id] = writer

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                f"/messages/?session_id={session_id.hex}",
                json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
            )

        assert response.status_code == 401
        payload = response.json()
        assert payload["error"] == "unauthorized"

    async def test_invalid_bearer_token_post_messages_is_rejected_with_401(
        self, dual_tenant_app
    ) -> None:
        """A POST to /messages/ with an invalid Bearer token must be rejected with 401."""
        app, creds = dual_tenant_app
        session_id = uuid.uuid4()

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                f"/messages/?session_id={session_id.hex}",
                headers={"Authorization": "Bearer not-a-valid-token"},
                json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
            )

        assert response.status_code == 401
        assert response.json()["error"] == "unauthorized"

    async def test_cross_tenant_session_post_messages_is_rejected_with_403(
        self, dual_tenant_app
    ) -> None:
        """A valid Bearer token from Tenant B must NEVER be able to inject messages
        into a session established by Tenant A. It must be rejected with 403 Forbidden.
        """
        app, creds = dual_tenant_app
        transport = creds["transport"]

        session_id = uuid.uuid4()
        writer, reader = anyio.create_memory_object_stream(10)
        transport._read_stream_writers[session_id] = writer

        # Tenant A created the session
        from mcp.server.auth.middleware.bearer_auth import (
            AccessToken,
            AuthenticatedUser,
            authorization_context,
        )

        user_a = AuthenticatedUser(
            AccessToken(
                token=creds["key_id_a"],
                client_id=creds["org_a"].id,
                scopes=["whitepact:review"],
                subject=creds["key_id_a"],
                claims={"iss": creds["org_a"].id},
            )
        )
        transport._session_owners[session_id] = authorization_context(user_a)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Tenant B attempts to hijack Tenant A's session
            response = await client.post(
                f"/messages/?session_id={session_id.hex}",
                headers={"Authorization": f"Bearer {creds['key_b']}"},
                json={"jsonrpc": "2.0", "id": 100, "method": "ping"},
            )

        assert response.status_code == 403
        payload = response.json()
        assert payload["error"] in {"forbidden", "cross_tenant_forbidden"}
        # Ensure no message was placed in the writer stream
        with pytest.raises(anyio.WouldBlock):
            reader.receive_nowait()

    async def test_mismatched_key_in_same_tenant_is_rejected(self, dual_tenant_app) -> None:
        """A different API key within the same tenant must not hijack an existing session
        bound to a specific session owner.
        """
        app, creds = dual_tenant_app
        transport = creds["transport"]

        session_id = uuid.uuid4()
        writer, reader = anyio.create_memory_object_stream(10)
        transport._read_stream_writers[session_id] = writer

        from mcp.server.auth.middleware.bearer_auth import (
            AccessToken,
            AuthenticatedUser,
            authorization_context,
        )

        user_a = AuthenticatedUser(
            AccessToken(
                token=creds["key_id_a"],
                client_id=creds["org_a"].id,
                scopes=["whitepact:review"],
                subject=creds["key_id_a"],
                claims={"iss": creds["org_a"].id},
            )
        )
        transport._session_owners[session_id] = authorization_context(user_a)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                f"/messages/?session_id={session_id.hex}",
                headers={"Authorization": f"Bearer {creds['key_a_analyst']}"},
                json={"jsonrpc": "2.0", "id": 200, "method": "ping"},
            )

        assert response.status_code in {403, 404}
        with pytest.raises(anyio.WouldBlock):
            reader.receive_nowait()

    async def test_legitimate_session_owner_can_post_messages(self, dual_tenant_app) -> None:
        """The authenticated session owner presenting their valid credential must succeed
        and receive 202 Accepted.
        """
        app, creds = dual_tenant_app
        transport = creds["transport"]

        session_id = uuid.uuid4()
        writer, reader = anyio.create_memory_object_stream(10)
        transport._read_stream_writers[session_id] = writer

        from mcp.server.auth.middleware.bearer_auth import (
            AccessToken,
            AuthenticatedUser,
            authorization_context,
        )

        user_a = AuthenticatedUser(
            AccessToken(
                token=creds["key_id_a"],
                client_id=creds["org_a"].id,
                scopes=["whitepact:review"],
                subject=creds["key_id_a"],
                claims={"iss": creds["org_a"].id},
            )
        )
        transport._session_owners[session_id] = authorization_context(user_a)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                f"/messages/?session_id={session_id.hex}",
                headers={"Authorization": f"Bearer {creds['key_a']}"},
                json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
            )

        assert response.status_code == 202
        msg = reader.receive_nowait()
        assert msg.message.root.method == "ping"

    async def test_missing_session_id_returns_400(self, dual_tenant_app) -> None:
        """A POST without session_id query param must return 400 Bad Request."""
        app, creds = dual_tenant_app

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/messages/",
                headers={"Authorization": f"Bearer {creds['key_a']}"},
                json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
            )

        assert response.status_code == 400

    async def test_nonexistent_session_id_returns_404(self, dual_tenant_app) -> None:
        """A POST with a nonexistent session ID must return 404 Not Found."""
        app, creds = dual_tenant_app
        unknown_id = uuid.uuid4()

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                f"/messages/?session_id={unknown_id.hex}",
                headers={"Authorization": f"Bearer {creds['key_a']}"},
                json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
            )

        assert response.status_code == 404
