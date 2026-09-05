# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""End-to-end tests for WhitePact's ChatGPT OAuth 2.1 authorization server."""

from __future__ import annotations

import hashlib
import secrets
from base64 import urlsafe_b64encode
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from asgi_lifespan import LifespanManager
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from sqlalchemy import select, update

from responsibleai.dashboard.config import Settings
from responsibleai.db import OrgRepository, create_engine
from responsibleai.db.engine import oauth_auth_events, oauth_clients, oauth_credentials
from responsibleai.rbac.models import Plan, Role

ISSUER = "https://testserver"
RESOURCE = "https://testserver/mcp"
REDIRECT_URI = "https://chatgpt.com/connector_platform_oauth_redirect"
REVIEW_SCOPE = "whitepact:review"


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = urlsafe_b64encode(digest).decode().rstrip("=")
    return verifier, challenge


@pytest.fixture()
async def oauth_app(monkeypatch: pytest.MonkeyPatch):
    import responsibleai.dashboard.config as config_module
    import responsibleai.db as db_module
    from responsibleai.mcp.server import _build_http_app

    engine = create_engine(":memory:")
    await engine.init()
    monkeypatch.setattr(db_module, "create_engine", lambda _url: engine)
    monkeypatch.setenv("RAI_MCP_HTTP_AUTH_MAX_FAILURES", "100")
    settings = Settings(
        mcp_oauth_issuer=ISSUER,
        mcp_oauth_resource_uri=RESOURCE,
        mcp_oauth_scopes=[REVIEW_SCOPE, "offline_access"],
        mcp_oauth_access_token_ttl_seconds=900,
        mcp_oauth_refresh_token_ttl_seconds=2_592_000,
    )
    monkeypatch.setattr(config_module, "get_settings", lambda: settings)

    org_repo = OrgRepository(engine)
    reviewer_org = await org_repo.create_org(
        "OpenAI Reviewer", "openai-reviewer", plan=Plan.ENTERPRISE
    )
    key_record, reviewer_key = await org_repo.create_key(
        reviewer_org.id, "reviewer", role=Role.VIEWER
    )
    other_org = await org_repo.create_org("Other", "other", plan=Plan.ENTERPRISE)

    app = _build_http_app()
    manager = LifespanManager(app)
    await manager.__aenter__()
    yield manager.app, engine, reviewer_org, other_org, key_record, reviewer_key
    await manager.__aexit__(None, None, None)
    await engine.close()


def _client(app, token: str | None = None) -> httpx.AsyncClient:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url=ISSUER,
        headers=headers,
        follow_redirects=False,
    )


async def _register(client: httpx.AsyncClient) -> str:
    response = await client.post(
        "/oauth/register",
        json={
            "client_name": "ChatGPT WhitePact",
            "redirect_uris": [REDIRECT_URI],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["client_id"]


async def _authorize(
    client: httpx.AsyncClient,
    client_id: str,
    reviewer_key: str,
    *,
    scope: str = f"{REVIEW_SCOPE} offline_access",
    state: str = "expected-state",
) -> tuple[str, str]:
    verifier, challenge = _pkce()
    start = await client.get(
        "/oauth/authorize",
        params={
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "scope": scope,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "resource": RESOURCE,
        },
    )
    assert start.status_code == 200, start.text
    request_id = start.headers["x-whitepact-oauth-request-id"]
    finish = await client.post(
        "/oauth/authorize",
        data={"request_id": request_id, "api_key": reviewer_key, "action": "allow"},
    )
    assert finish.status_code == 303, finish.text
    query = parse_qs(urlparse(finish.headers["location"]).query)
    assert query["state"] == [state]
    assert query["iss"] == [ISSUER]
    return query["code"][0], verifier


async def _tokens(
    client: httpx.AsyncClient, client_id: str, code: str, verifier: str
) -> dict[str, object]:
    response = await client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": verifier,
            "resource": RESOURCE,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _complete_flow(app, reviewer_key: str) -> tuple[str, dict[str, object]]:
    async with _client(app) as client:
        client_id = await _register(client)
        code, verifier = await _authorize(client, client_id, reviewer_key)
        return client_id, await _tokens(client, client_id, code, verifier)


class TestDiscoveryAndAuthorization:
    async def test_discovery_metadata_is_oauth_21_pkce_and_resource_bound(self, oauth_app) -> None:
        app, *_ = oauth_app
        async with _client(app) as client:
            protected = await client.get("/.well-known/oauth-protected-resource")
            authorization = await client.get("/.well-known/oauth-authorization-server")
        assert protected.status_code == 200
        assert protected.json()["resource"] == RESOURCE
        assert protected.json()["authorization_servers"] == [ISSUER]
        metadata = authorization.json()
        assert metadata["issuer"] == ISSUER
        assert metadata["code_challenge_methods_supported"] == ["S256"]
        assert metadata["token_endpoint_auth_methods_supported"] == ["none"]
        assert metadata["authorization_response_iss_parameter_supported"] is True

    async def test_unauthenticated_mcp_is_401_with_oauth_challenge(self, oauth_app) -> None:
        app, *_ = oauth_app
        async with _client(app) as client:
            response = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
        assert response.status_code == 401
        challenge = response.headers["www-authenticate"]
        assert "resource_metadata=" in challenge
        assert f'scope="{REVIEW_SCOPE}"' in challenge

    @pytest.mark.parametrize(
        ("redirect_uri", "challenge_method", "resource"),
        [
            ("https://attacker.example/callback", "S256", RESOURCE),
            (REDIRECT_URI, "plain", RESOURCE),
            (REDIRECT_URI, "S256", "https://wrong.example/mcp"),
        ],
    )
    async def test_redirect_pkce_downgrade_and_wrong_audience_are_denied(
        self, oauth_app, redirect_uri: str, challenge_method: str, resource: str
    ) -> None:
        app, *_ = oauth_app
        async with _client(app) as client:
            client_id = await _register(client)
            _verifier, challenge = _pkce()
            response = await client.get(
                "/oauth/authorize",
                params={
                    "response_type": "code",
                    "client_id": client_id,
                    "redirect_uri": redirect_uri,
                    "scope": REVIEW_SCOPE,
                    "state": "state",
                    "code_challenge": challenge,
                    "code_challenge_method": challenge_method,
                    "resource": resource,
                },
            )
        assert response.status_code == 400

    async def test_admin_api_key_cannot_be_used_as_reviewer_login(self, oauth_app) -> None:
        app, _engine, reviewer_org, *_ = oauth_app
        repo = OrgRepository(_engine)
        _record, admin_key = await repo.create_key(reviewer_org.id, "admin", role=Role.ADMIN)
        async with _client(app) as client:
            client_id = await _register(client)
            verifier, challenge = _pkce()
            start = await client.get(
                "/oauth/authorize",
                params={
                    "response_type": "code",
                    "client_id": client_id,
                    "redirect_uri": REDIRECT_URI,
                    "scope": REVIEW_SCOPE,
                    "state": "state",
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                    "resource": RESOURCE,
                },
            )
            response = await client.post(
                "/oauth/authorize",
                data={
                    "request_id": start.headers["x-whitepact-oauth-request-id"],
                    "api_key": admin_key,
                    "action": "allow",
                },
            )
        assert response.status_code == 403
        assert verifier not in response.text

    async def test_malformed_header_and_query_token_do_not_authenticate(self, oauth_app) -> None:
        app, *_rest, reviewer_key = oauth_app
        _client_id, tokens = await _complete_flow(app, reviewer_key)
        access_token = str(tokens["access_token"])
        async with _client(app) as client:
            malformed = await client.post(
                "/mcp", headers={"Authorization": f"Basic {access_token}"}
            )
            query = await client.post(f"/mcp?access_token={access_token}")
        assert malformed.status_code == 401
        assert query.status_code == 401
        assert access_token not in malformed.text
        assert access_token not in query.text


class TestTokenLifecycleAndTenantBinding:
    async def test_valid_code_refresh_rotation_and_replay_revocation(self, oauth_app) -> None:
        app, *_rest, reviewer_key = oauth_app
        client_id, tokens = await _complete_flow(app, reviewer_key)
        assert tokens["token_type"] == "Bearer"
        assert tokens["expires_in"] == 900
        assert "refresh_token" in tokens
        old_refresh = str(tokens["refresh_token"])
        async with _client(app) as client:
            refreshed = await client.post(
                "/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": client_id,
                    "refresh_token": old_refresh,
                    "resource": RESOURCE,
                },
            )
            replay = await client.post(
                "/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": client_id,
                    "refresh_token": old_refresh,
                    "resource": RESOURCE,
                },
            )
        assert refreshed.status_code == 200
        assert refreshed.json()["refresh_token"] != old_refresh
        assert replay.status_code == 400
        async with _client(app, str(refreshed.json()["access_token"])) as client:
            denied = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
        assert denied.status_code == 401

    async def test_revoked_and_expired_access_tokens_are_denied(self, oauth_app) -> None:
        app, engine, *_rest, reviewer_key = oauth_app
        _client_id, tokens = await _complete_flow(app, reviewer_key)
        access_token = str(tokens["access_token"])
        async with _client(app) as client:
            revoked = await client.post(
                "/oauth/revoke", data={"token": access_token, "token_type_hint": "access_token"}
            )
        assert revoked.status_code == 200
        async with _client(app, access_token) as client:
            denied = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
        assert denied.status_code == 401

        _client_id, second = await _complete_flow(app, reviewer_key)
        second_access = str(second["access_token"])
        async with engine.raw.begin() as connection:
            await connection.execute(
                update(oauth_credentials)
                .where(
                    oauth_credentials.c.token_hash
                    == hashlib.sha256(second_access.encode()).hexdigest()
                )
                .values(expires_at="2000-01-01T00:00:00+00:00")
            )
        async with _client(app, second_access) as client:
            expired = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
        assert expired.status_code == 401

    async def test_oauth_identity_is_bound_to_reviewer_org_not_other_org(self, oauth_app) -> None:
        app, engine, reviewer_org, other_org, key_record, reviewer_key = oauth_app
        _client_id, tokens = await _complete_flow(app, reviewer_key)
        access_token = str(tokens["access_token"])
        async with engine.raw.connect() as connection:
            credential = (
                await connection.execute(
                    select(oauth_credentials).where(
                        oauth_credentials.c.token_hash
                        == hashlib.sha256(access_token.encode()).hexdigest()
                    )
                )
            ).fetchone()
        assert credential is not None
        assert credential.org_id == reviewer_org.id
        assert credential.org_id != other_org.id
        assert credential.subject_id == key_record.id
        assert credential.role == "VIEWER"

    async def test_cross_tenant_token_substitution_is_denied(self, oauth_app) -> None:
        app, engine, _reviewer_org, other_org, _key_record, reviewer_key = oauth_app
        _client_id, tokens = await _complete_flow(app, reviewer_key)
        access_token = str(tokens["access_token"])
        async with engine.raw.begin() as connection:
            await connection.execute(
                update(oauth_credentials)
                .where(
                    oauth_credentials.c.token_hash
                    == hashlib.sha256(access_token.encode()).hexdigest()
                )
                .values(org_id=other_org.id)
            )
        async with _client(app, access_token) as client:
            response = await client.post("/mcp")
        assert response.status_code == 401

    async def test_wrong_audience_token_is_denied(self, oauth_app) -> None:
        app, engine, *_rest, reviewer_key = oauth_app
        _client_id, tokens = await _complete_flow(app, reviewer_key)
        access_token = str(tokens["access_token"])
        async with engine.raw.begin() as connection:
            await connection.execute(
                update(oauth_credentials)
                .where(
                    oauth_credentials.c.token_hash
                    == hashlib.sha256(access_token.encode()).hexdigest()
                )
                .values(resource="https://wrong.example/mcp")
            )
        async with _client(app, access_token) as client:
            response = await client.post("/mcp")
        assert response.status_code == 401

    async def test_revoked_client_cannot_refresh(self, oauth_app) -> None:
        app, engine, *_rest, reviewer_key = oauth_app
        client_id, tokens = await _complete_flow(app, reviewer_key)
        async with engine.raw.begin() as connection:
            await connection.execute(
                update(oauth_clients)
                .where(oauth_clients.c.client_id == client_id)
                .values(revoked=1)
            )
        async with _client(app) as client:
            response = await client.post(
                "/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": client_id,
                    "refresh_token": str(tokens["refresh_token"]),
                    "resource": RESOURCE,
                },
            )
        assert response.status_code == 400

    async def test_authorization_request_and_code_are_one_use(self, oauth_app) -> None:
        app, *_rest, reviewer_key = oauth_app
        async with _client(app) as client:
            client_id = await _register(client)
            code, verifier = await _authorize(client, client_id, reviewer_key)
            first = await _tokens(client, client_id, code, verifier)
            replay = await client.post(
                "/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": client_id,
                    "code": code,
                    "redirect_uri": REDIRECT_URI,
                    "code_verifier": verifier,
                    "resource": RESOURCE,
                },
            )
        assert first["access_token"]
        assert replay.status_code == 400

    async def test_authorization_code_cannot_be_substituted_between_clients(
        self, oauth_app
    ) -> None:
        app, *_rest, reviewer_key = oauth_app
        async with _client(app) as client:
            legitimate_client = await _register(client)
            other_client = await _register(client)
            code, verifier = await _authorize(client, legitimate_client, reviewer_key)
            substituted = await client.post(
                "/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": other_client,
                    "code": code,
                    "redirect_uri": REDIRECT_URI,
                    "code_verifier": verifier,
                    "resource": RESOURCE,
                },
            )
            legitimate = await _tokens(client, legitimate_client, code, verifier)
        assert substituted.status_code == 400
        assert legitimate["access_token"]

    async def test_static_api_key_and_oauth_token_types_remain_unambiguous(self, oauth_app) -> None:
        app, *_rest, reviewer_key = oauth_app
        _client_id, tokens = await _complete_flow(app, reviewer_key)
        async with _client(app, reviewer_key) as api_client:
            api_response = await api_client.post("/mcp")
        async with _client(app, str(tokens["access_token"])) as oauth_client:
            oauth_response = await oauth_client.post("/mcp")
        assert api_response.status_code != 401
        assert oauth_response.status_code != 401


class TestAuthenticatedMcpReview:
    async def test_initialize_inventory_and_review_tools(self, oauth_app) -> None:
        app, *_rest, reviewer_key = oauth_app
        _client_id, tokens = await _complete_flow(app, reviewer_key)
        access_token = str(tokens["access_token"])
        calls = {
            "rai_health": {},
            "rai_scan": {
                "text": "Contact John at john@example.com or 555-123-4567. His employee ID is EMP-2048.",
                "redact": True,
            },
            "rai_trust_score": {
                "fairness": 0.80,
                "privacy": 0.90,
                "security": 0.70,
                "robustness": 0.85,
                "compliance": 0.90,
                "authenticity": 0.95,
            },
            "rai_eu_ai_act_classify": {
                "system_description": "An automated resume-screening system used by employers to rank candidates and decide who proceeds to interviews.",
                "deployment_sector": "employment",
                "affects_natural_persons": True,
                "is_fully_automated": True,
            },
            "rai_hallucination": {
                "source": "The project review meeting is scheduled for Tuesday at 3 PM.",
                "text": "The project review meeting is scheduled for Wednesday at 3 PM.",
            },
        }
        async with _client(app, access_token) as http_client:
            async with streamable_http_client("/mcp", http_client=http_client) as streams:
                async with ClientSession(streams[0], streams[1]) as session:
                    await session.initialize()
                    tools = (await session.list_tools()).tools
                    resources = (await session.list_resources()).resources
                    results = {
                        name: await session.call_tool(name, arguments)
                        for name, arguments in calls.items()
                    }
        assert len(tools) == 30
        assert len(resources) == 20
        assert all(result.isError is not True for result in results.values())
        assert all(
            tool.model_extra
            and tool.model_extra["securitySchemes"]
            == [{"type": "oauth2", "scopes": [REVIEW_SCOPE]}]
            for tool in tools
        )
        assert all(
            tool.meta
            and tool.meta["securitySchemes"] == [{"type": "oauth2", "scopes": [REVIEW_SCOPE]}]
            for tool in tools
        )

    async def test_forged_bearer_and_missing_scope_are_denied(self, oauth_app) -> None:
        app, *_rest, reviewer_key = oauth_app
        async with _client(app, "wp_at_forged") as client:
            forged = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
        assert forged.status_code == 401

        async with _client(app) as client:
            client_id = await _register(client)
            code, verifier = await _authorize(
                client, client_id, reviewer_key, scope="offline_access"
            )
            tokens = await _tokens(client, client_id, code, verifier)
        async with _client(app, str(tokens["access_token"])) as client:
            insufficient = await client.post(
                "/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"}
            )
        assert insufficient.status_code == 403

    async def test_tokens_never_appear_in_errors_or_logs(
        self, oauth_app, caplog: pytest.LogCaptureFixture
    ) -> None:
        app, *_ = oauth_app
        secret = "wp_at_this-must-never-be-logged"
        async with _client(app, secret) as client:
            response = await client.post("/mcp", content=b"not-json")
        assert secret not in response.text
        assert secret not in caplog.text

    async def test_auth_audit_events_contain_no_credential_material(self, oauth_app) -> None:
        app, engine, *_rest, reviewer_key = oauth_app
        _client_id, tokens = await _complete_flow(app, reviewer_key)
        access_token = str(tokens["access_token"])
        async with _client(app, access_token) as client:
            response = await client.post("/mcp")
        assert response.status_code != 401
        async with _client(app, "wp_at_forged-audit-probe") as client:
            denied = await client.post("/mcp")
        assert denied.status_code == 401
        async with engine.raw.connect() as connection:
            rows = (await connection.execute(select(oauth_auth_events))).fetchall()
        serialized = repr([dict(row._mapping) for row in rows])
        assert access_token not in serialized
        assert "wp_at_forged-audit-probe" not in serialized
        assert {row.outcome for row in rows} >= {"success", "invalid_token"}
