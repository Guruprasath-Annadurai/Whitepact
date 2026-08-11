"""Integration tests for the hosted MCP HTTP app — both the modern
Streamable HTTP transport (`/mcp`) and the legacy HTTP+SSE transport
(`/sse` + `/messages/`) built by `responsibleai.mcp.server._build_http_app`.

These run a real MCP client against the real Starlette ASGI app in-process
(via `httpx.ASGITransport` — no socket), proving actual protocol interop
rather than just exercising `_call_tool` directly (that's what
test_mcp_server_gating.py already covers). MIGRATION_WHITEPACT_V2.md
Section 7: Streamable HTTP is the new, preferred hosted transport; SSE
keeps running unmodified for existing clients.
"""

from __future__ import annotations

import httpx
import pytest
from asgi_lifespan import LifespanManager
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from responsibleai.db import OrgRepository, create_engine
from responsibleai.rbac.models import Plan, Role


@pytest.fixture()
async def seeded_app(monkeypatch: pytest.MonkeyPatch):
    """Build the real hosted-MCP Starlette app, with its internal DB engine
    swapped for one the test can also seed an org/API key into. Patching
    `responsibleai.db.create_engine` works because `_build_http_app` does a
    local `from responsibleai.db import ... create_engine` on each call, so
    it picks up whatever the module attribute resolves to at call time."""
    import responsibleai.db as db_module
    from responsibleai.mcp.server import _build_http_app

    engine = create_engine(":memory:")
    await engine.init()
    monkeypatch.setattr(db_module, "create_engine", lambda _url: engine)

    org_repo = OrgRepository(engine)
    org = await org_repo.create_org("Acme", "acme", plan=Plan.ENTERPRISE)
    _key_rec, raw_key = await org_repo.create_key(org.id, "test-key", role=Role.ANALYST)

    app = _build_http_app()
    async with LifespanManager(app) as manager:
        yield manager.app, raw_key

    await engine.close()


def _asgi_http_client(app, raw_key: str) -> httpx.AsyncClient:
    """An httpx.AsyncClient wired to the in-process ASGI app (no socket),
    pre-authenticated, for handing straight to `streamable_http_client`."""
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": f"Bearer {raw_key}"},
    )


async def _raw_client(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


class TestStreamableHttpTransport:
    async def test_unauthenticated_request_is_rejected(self, seeded_app) -> None:
        app, _raw_key = seeded_app
        async with await _raw_client(app) as client:
            response = await client.post("/mcp", json={"jsonrpc": "2.0", "method": "ping", "id": 1})
        assert response.status_code == 401
        assert response.json()["error"] == "unauthorized"

    async def test_invalid_bearer_token_is_rejected(self, seeded_app) -> None:
        app, _raw_key = seeded_app
        async with await _raw_client(app) as client:
            response = await client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "method": "ping", "id": 1},
                headers={"Authorization": "Bearer not-a-real-key"},
            )
        assert response.status_code == 401

    async def test_initialize_and_list_tools_over_streamable_http(self, seeded_app) -> None:
        app, raw_key = seeded_app
        async with (
            _asgi_http_client(app, raw_key) as http_client,
            streamable_http_client("/mcp", http_client=http_client) as (
                read_stream, write_stream, _get_session_id,
            ),
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.list_tools()

        names = {t.name for t in result.tools}
        assert "rai_health" in names
        assert len(result.tools) == 27

    async def test_call_tool_over_streamable_http(self, seeded_app) -> None:
        app, raw_key = seeded_app
        async with (
            _asgi_http_client(app, raw_key) as http_client,
            streamable_http_client("/mcp", http_client=http_client) as (
                read_stream, write_stream, _get_session_id,
            ),
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool("rai_health", {})

        assert result.isError is not True


class TestLegacySseTransportUnaffected:
    """The legacy /sse + /messages/ transport must keep working exactly as
    before — Streamable HTTP is additive, not a replacement."""

    async def test_sse_requires_auth(self, seeded_app) -> None:
        app, _raw_key = seeded_app
        async with await _raw_client(app) as client:
            response = await client.get("/sse")
        assert response.status_code == 401
        assert response.json()["error"] == "unauthorized"

    async def test_sse_rejects_invalid_bearer_token(self, seeded_app) -> None:
        app, _raw_key = seeded_app
        async with await _raw_client(app) as client:
            response = await client.get("/sse", headers={"Authorization": "Bearer not-a-real-key"})
        assert response.status_code == 401


class TestHealthEndpoint:
    async def test_health_lists_both_transports(self, seeded_app) -> None:
        app, _raw_key = seeded_app
        async with await _raw_client(app) as client:
            response = await client.get("/health")
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["transport"] == "http+sse"
        assert set(payload["transports"]) == {"streamable-http", "http+sse"}
        assert payload["tools"] == 27
