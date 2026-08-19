"""Tests for the hosted MCP transports' OAuth/OIDC resource-server auth:
a Bearer JWT issued by the org's configured OIDC provider authenticates
`/mcp` and `/sse` exactly like the dashboard API already accepts it,
plus the RFC 9728 protected-resource-metadata discovery endpoint and
the `WWW-Authenticate` hint on `401`s. See MIGRATION_WHITEPACT_V2.md's
MCP authorization section for the rationale (resource server against
the org's existing Authorization Server, not a new one).
"""

from __future__ import annotations

import asyncio
import base64
import json

import httpx
import pytest
from asgi_lifespan import LifespanManager
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from responsibleai.dashboard.config import Settings
from responsibleai.db import OrgRepository, create_engine
from responsibleai.rbac.models import Plan, Role


def _make_jwt(payload: dict) -> str:
    header = base64.urlsafe_b64encode(json.dumps({"alg": "RS256"}).encode()).decode().rstrip("=")
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"{header}.{body}.fakesig"


@pytest.fixture()
async def mcp_app(monkeypatch: pytest.MonkeyPatch):
    """Yields (build, org_id, raw_api_key). `await build(oidc_issuer=...)`
    constructs a fresh hosted-MCP app with that OIDC config — settings are
    injected directly (bypassing env vars and the `get_settings()` cache)
    since `_build_http_app` reads `get_settings` fresh from
    `responsibleai.dashboard.config` on each call."""
    import responsibleai.dashboard.config as config_module
    import responsibleai.db as db_module
    from responsibleai.mcp.server import _build_http_app

    engine = create_engine(":memory:")
    await engine.init()
    monkeypatch.setattr(db_module, "create_engine", lambda _url: engine)

    org_repo = OrgRepository(engine)
    org = await org_repo.create_org("Acme", "acme", plan=Plan.ENTERPRISE)
    _key_rec, raw_key = await org_repo.create_key(org.id, "test-key", role=Role.ANALYST)

    built = []

    async def _build(*, oidc_issuer: str | None = None, oidc_client_id: str = "mcp-client"):
        settings = Settings(
            oidc_issuer=oidc_issuer,
            oidc_client_id=oidc_client_id,
            oidc_skip_verification=True,
        )
        monkeypatch.setattr(config_module, "get_settings", lambda: settings)
        app = _build_http_app()
        manager = LifespanManager(app)
        await manager.__aenter__()
        built.append(manager)
        return manager.app

    yield _build, org.id, raw_key

    for manager in built:
        await manager.__aexit__(None, None, None)
    await engine.close()


async def _raw_client(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


def _asgi_http_client(app, token: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": f"Bearer {token}"},
    )


async def _list_tools_over_mcp(app, token: str) -> list:
    """A real MCP client round trip through /mcp — not a raw JSON-RPC POST,
    since an authenticated-but-unrecognized request (e.g. a bare "ping"
    method) leaves the StreamableHTTPSessionManager waiting on a response
    stream that a plain httpx.post never drives to completion."""
    async with streamable_http_client(
        "/mcp",
        http_client=_asgi_http_client(app, token),
    ) as (read_stream, write_stream, _get_session_id):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.list_tools()
    return result.tools


class TestOidcJwtAuth:
    async def test_valid_jwt_authenticates_mcp(self, mcp_app) -> None:
        build, org_id, _raw_key = mcp_app
        app = await build(oidc_issuer="https://idp.example.com")
        token = _make_jwt({"sub": "user-1", "org_id": org_id, "roles": ["ANALYST"]})
        tools = await _list_tools_over_mcp(app, token)
        assert len(tools) == 29

    async def test_valid_jwt_authenticates_sse(self, mcp_app) -> None:
        """A rejected request (401) returns immediately; a successfully
        authenticated one enters `sse.connect_sse` and blocks forever
        holding the stream open (by design -- SSE has no natural end),
        which httpx's in-process ASGITransport can't partially observe
        the way a real socket client streaming headers-then-body can. So
        the proof of success here is deliberately indirect: the request
        does NOT finish within a short deadline, meaning auth passed and
        the transport moved on to holding the connection open rather than
        rejecting it outright."""
        build, org_id, _raw_key = mcp_app
        app = await build(oidc_issuer="https://idp.example.com")
        token = _make_jwt({"sub": "user-1", "org_id": org_id, "roles": ["ANALYST"]})
        async with await _raw_client(app) as client:
            with pytest.raises(TimeoutError):
                async with asyncio.timeout(0.5):
                    await client.get("/sse", headers={"Authorization": f"Bearer {token}"})

    async def test_unknown_org_id_falls_back_to_free_plan(self, mcp_app) -> None:
        """A JWT with an org_id the DB doesn't know about still
        authenticates (identity is proven by the token signature/issuer,
        not by DB membership) but gets no elevated plan. A FREE-plan
        context has zero hosted quota (see mcp/licensing.py), so `rai_health`
        -- otherwise free -- comes back as `hosted_access_unavailable`
        rather than a 401/429: proof auth succeeded and plan-gating, not
        rejection, is what's shaping the response."""
        build, _org_id, _raw_key = mcp_app
        app = await build(oidc_issuer="https://idp.example.com")
        token = _make_jwt({"sub": "user-2", "org_id": "org-does-not-exist", "roles": []})
        async with streamable_http_client(
            "/mcp",
            http_client=_asgi_http_client(app, token),
        ) as (read_stream, write_stream, _get_session_id):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool("rai_health", {})
        payload = json.loads(result.content[0].text)
        assert payload["error"] == "hosted_access_unavailable"

    async def test_static_api_key_still_works_when_oidc_configured(self, mcp_app) -> None:
        """rai_-prefixed tokens are never treated as JWTs, even with OIDC
        configured — the two credential kinds stay unambiguous."""
        build, _org_id, raw_key = mcp_app
        app = await build(oidc_issuer="https://idp.example.com")
        tools = await _list_tools_over_mcp(app, raw_key)
        assert len(tools) == 29

    async def test_malformed_bearer_token_rejected(self, mcp_app) -> None:
        build, _org_id, _raw_key = mcp_app
        app = await build(oidc_issuer="https://idp.example.com")
        async with await _raw_client(app) as client:
            response = await client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "method": "ping", "id": 1},
                headers={"Authorization": "Bearer not-a-jwt-or-a-key"},
            )
        assert response.status_code == 401

    async def test_no_oidc_configured_jwt_rejected(self, mcp_app) -> None:
        """Without oidc_issuer set, a JWT-shaped token is just an invalid
        static key — no OIDC provider exists to try it against."""
        build, org_id, _raw_key = mcp_app
        app = await build(oidc_issuer=None)
        token = _make_jwt({"sub": "user-1", "org_id": org_id, "roles": ["ANALYST"]})
        async with await _raw_client(app) as client:
            response = await client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "method": "ping", "id": 1},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 401


class TestWwwAuthenticateHeader:
    async def test_401_includes_resource_metadata_hint_when_oidc_configured(self, mcp_app) -> None:
        build, _org_id, _raw_key = mcp_app
        app = await build(oidc_issuer="https://idp.example.com")
        async with await _raw_client(app) as client:
            response = await client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "method": "ping", "id": 1},
            )
        assert response.status_code == 401
        www_auth = response.headers.get("www-authenticate", "")
        assert "resource_metadata=" in www_auth
        assert "/.well-known/oauth-protected-resource" in www_auth

    async def test_401_has_no_hint_when_oidc_not_configured(self, mcp_app) -> None:
        build, _org_id, _raw_key = mcp_app
        app = await build(oidc_issuer=None)
        async with await _raw_client(app) as client:
            response = await client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "method": "ping", "id": 1},
            )
        assert response.status_code == 401
        assert "www-authenticate" not in {k.lower() for k in response.headers}


class TestProtectedResourceMetadata:
    async def test_returns_metadata_when_oidc_configured(self, mcp_app) -> None:
        build, _org_id, _raw_key = mcp_app
        app = await build(oidc_issuer="https://idp.example.com")
        async with await _raw_client(app) as client:
            response = await client.get("/.well-known/oauth-protected-resource")
        assert response.status_code == 200
        payload = response.json()
        assert payload["authorization_servers"] == ["https://idp.example.com"]
        assert payload["resource"].endswith("/mcp")

    async def test_404_when_oidc_not_configured(self, mcp_app) -> None:
        build, _org_id, _raw_key = mcp_app
        app = await build(oidc_issuer=None)
        async with await _raw_client(app) as client:
            response = await client.get("/.well-known/oauth-protected-resource")
        assert response.status_code == 404
