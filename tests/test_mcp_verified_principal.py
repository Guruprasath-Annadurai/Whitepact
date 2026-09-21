# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real MCP protocol round-trip tests for Verified Principal
(Authority Everywhere Phase 3): a Bearer VC-JWT presentation
authenticates `/mcp` exactly like an OIDC JWT already does (see
test_mcp_oauth.py, whose fixture/helper shapes this file mirrors), and
a successful verification is recorded in `verified_principals` via
`PrincipalRepository`.
"""

from __future__ import annotations

import base64
import json

import httpx
import pytest
from asgi_lifespan import LifespanManager
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from responsibleai.dashboard.config import Settings
from responsibleai.db import OrgRepository, PrincipalRepository, create_engine
from responsibleai.rbac.models import Plan, Role


def _make_vc_jwt(payload: dict) -> str:
    header = base64.urlsafe_b64encode(json.dumps({"alg": "RS256"}).encode()).decode().rstrip("=")
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"{header}.{body}.fakesig"


def _vc_payload(
    *,
    sub: str = "service-account-1",
    iss: str = "https://issuer.example.com",
    org_id: str | None = None,
    holder_kind: str = "service_account",
) -> dict:
    return {
        "sub": sub,
        "iss": iss,
        "vc": {
            "type": ["VerifiableCredential", "AuthorityEverywherePrincipal"],
            "credentialSubject": {
                "holderKind": holder_kind,
                "orgId": org_id,
                "roles": ["ANALYST"],
            },
        },
    }


@pytest.fixture()
async def mcp_app(monkeypatch: pytest.MonkeyPatch):
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

    async def _build(*, vc_trusted_issuers: list[str] | None = None):
        settings = Settings(
            vc_trusted_issuers=vc_trusted_issuers or [],
            vc_skip_verification=True,
        )
        monkeypatch.setattr(config_module, "get_settings", lambda: settings)
        app = _build_http_app()
        manager = LifespanManager(app)
        await manager.__aenter__()
        built.append(manager)
        return manager.app

    yield _build, org.id, raw_key, engine

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
    async with streamable_http_client(
        "/mcp",
        http_client=_asgi_http_client(app, token),
    ) as (read_stream, write_stream, _get_session_id):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.list_tools()
    return result.tools


class TestVerifiedPrincipalAuth:
    async def test_valid_vc_jwt_authenticates_mcp(self, mcp_app) -> None:
        build, org_id, _raw_key, _engine = mcp_app
        app = await build(vc_trusted_issuers=["https://issuer.example.com"])
        token = _make_vc_jwt(_vc_payload(org_id=org_id))
        tools = await _list_tools_over_mcp(app, token)
        assert len(tools) == 30

    async def test_verification_is_recorded_in_audit_trail(self, mcp_app) -> None:
        build, org_id, _raw_key, engine = mcp_app
        app = await build(vc_trusted_issuers=["https://issuer.example.com"])
        token = _make_vc_jwt(_vc_payload(sub="agent-99", org_id=org_id))
        await _list_tools_over_mcp(app, token)

        # Each authenticated request within the MCP session (session
        # init, list_tools, ...) re-runs `_authenticate` and records its
        # own claim -- this is a per-authentication audit log, not
        # deduplicated per session, so several rows for one token
        # presented across one client session is expected.
        principal_repo = PrincipalRepository(engine)
        claims = await principal_repo.get_recent_for_principal("agent-99")
        assert len(claims) >= 1
        assert claims[0].org_id == org_id
        assert claims[0].holder_kind == "service_account"
        assert claims[0].issuer == "https://issuer.example.com"

    async def test_untrusted_issuer_rejected(self, mcp_app) -> None:
        build, org_id, _raw_key, _engine = mcp_app
        app = await build(vc_trusted_issuers=["https://issuer.example.com"])
        token = _make_vc_jwt(_vc_payload(org_id=org_id, iss="https://untrusted.example.com"))
        async with await _raw_client(app) as client:
            response = await client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "method": "ping", "id": 1},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 401

    async def test_no_vc_issuers_configured_token_rejected(self, mcp_app) -> None:
        build, org_id, _raw_key, _engine = mcp_app
        app = await build(vc_trusted_issuers=None)
        token = _make_vc_jwt(_vc_payload(org_id=org_id))
        async with await _raw_client(app) as client:
            response = await client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "method": "ping", "id": 1},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 401

    async def test_static_api_key_still_works_when_vc_configured(self, mcp_app) -> None:
        build, _org_id, raw_key, _engine = mcp_app
        app = await build(vc_trusted_issuers=["https://issuer.example.com"])
        tools = await _list_tools_over_mcp(app, raw_key)
        assert len(tools) == 30

    async def test_oidc_jwt_not_misrouted_to_vc_path(self, mcp_app) -> None:
        """A plain OIDC-style JWT (no `vc` claim) never reaches the VC
        verifier -- `looks_like_vc_jwt` routes it away, and with no OIDC
        issuer configured in this fixture, it's simply rejected as an
        unrecognized bearer token."""
        build, org_id, _raw_key, _engine = mcp_app
        app = await build(vc_trusted_issuers=["https://issuer.example.com"])
        token = _make_vc_jwt({"sub": "user-1", "org_id": org_id, "roles": ["ANALYST"]})
        async with await _raw_client(app) as client:
            response = await client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "method": "ping", "id": 1},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 401
