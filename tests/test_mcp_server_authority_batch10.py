# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Batch 10: ``mcp/server.py`` auth/OAuth/transport deny paths and remaining
``runtime/authority_kernel.py`` fail-closed branches."""

from __future__ import annotations

import asyncio
import hashlib
import secrets
import uuid
from base64 import urlsafe_b64encode
from collections.abc import AsyncGenerator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from asgi_lifespan import LifespanManager
from sqlalchemy import select, update
from sqlalchemy.exc import OperationalError

from responsibleai.dashboard.config import Settings
from responsibleai.db.engine import create_engine
from responsibleai.db.engine import governance_execution_authorizations as auths
from responsibleai.db.engine import governance_execution_nonces as nonces
from responsibleai.db.engine import runtime_execution_attempts as attempts
from responsibleai.db.engine import runtime_execution_dispatch_outbox as outbox
from responsibleai.db.engine import runtime_execution_fences as fences
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from responsibleai.db.org_repository import OrgRepository
from responsibleai.db.revocation_epoch_repository import bump_epoch_on_connection
from responsibleai.mcp.server import (
    _AuthFailureLimiter,
    _build_http_app,
    _with_oauth_security,
)
from responsibleai.rbac.models import GovernanceStatus, Plan, Role
from responsibleai.runtime.authority_kernel import (
    Phase7AAuthorityKernel,
    QueueTicket,
    _is_deadlock,
)
from responsibleai.runtime.errors import (
    AuthorityDatabaseError,
    AuthorityKernelError,
    AuthorizationIneligibleError,
    CrossTenantAccessError,
    PreEffectCasRejected,
    StaleWorkerError,
)
from responsibleai.runtime.models import AttemptState, AuthorizationStatus, OutboxStatus
from tests.pg_test_url import isolated_pg_url

ISSUER = "https://testserver"
RESOURCE = f"{ISSUER}/mcp"
REDIRECT = "https://chatgpt.com/connector_platform_oauth_redirect"


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge


@pytest.fixture()
async def mcp_oauth_app(monkeypatch: pytest.MonkeyPatch):
    import responsibleai.dashboard.config as config_module
    import responsibleai.db as db_module

    engine = create_engine(":memory:")
    await engine.init()
    monkeypatch.setattr(db_module, "create_engine", lambda _url: engine)
    monkeypatch.setenv("RAI_MCP_HTTP_AUTH_MAX_FAILURES", "100")
    settings = Settings(
        mcp_oauth_issuer=ISSUER,
        mcp_oauth_resource_uri=RESOURCE,
        mcp_oauth_scopes=["whitepact:review", "offline_access"],
    )
    monkeypatch.setattr(config_module, "get_settings", lambda: settings)

    org_repo = OrgRepository(engine)
    org = await org_repo.create_org("Batch10", "batch10", plan=Plan.ENTERPRISE)
    _rec, raw_key = await org_repo.create_key(org.id, "analyst", role=Role.ANALYST)
    other = await org_repo.create_org("Other", "batch10-other", plan=Plan.ENTERPRISE)

    app = _build_http_app()
    manager = LifespanManager(app)
    await manager.__aenter__()
    try:
        yield manager.app, engine, org, other, raw_key
    finally:
        await manager.__aexit__(None, None, None)
        await engine.close()


@pytest.fixture()
async def mcp_api_only_app(monkeypatch: pytest.MonkeyPatch):
    import responsibleai.dashboard.config as config_module
    import responsibleai.db as db_module

    engine = create_engine(":memory:")
    await engine.init()
    monkeypatch.setattr(db_module, "create_engine", lambda _url: engine)
    monkeypatch.setattr(config_module, "get_settings", lambda: Settings(mcp_oauth_issuer=""))

    org_repo = OrgRepository(engine)
    org = await org_repo.create_org("ApiOnly", "api-only", plan=Plan.ENTERPRISE)
    _rec, raw_key = await org_repo.create_key(org.id, "key", role=Role.ANALYST)

    app = _build_http_app()
    manager = LifespanManager(app)
    await manager.__aenter__()
    try:
        yield manager.app, raw_key
    finally:
        await manager.__aexit__(None, None, None)
        await engine.close()


@pytest.fixture()
async def mcp_oidc_resource_app(monkeypatch: pytest.MonkeyPatch):
    import responsibleai.dashboard.config as config_module
    import responsibleai.db as db_module

    engine = create_engine(":memory:")
    await engine.init()
    monkeypatch.setattr(db_module, "create_engine", lambda _url: engine)
    settings = Settings(
        mcp_oauth_issuer="",
        oidc_issuer="https://idp.example",
        oidc_client_id="mcp-client",
        oidc_skip_verification=True,
    )
    monkeypatch.setattr(config_module, "get_settings", lambda: settings)

    app = _build_http_app()
    manager = LifespanManager(app)
    await manager.__aenter__()
    try:
        yield manager.app
    finally:
        await manager.__aexit__(None, None, None)
        await engine.close()


@pytest.fixture
async def pg_url() -> AsyncGenerator[str, None]:
    async for url in isolated_pg_url("wp_batch10_kern"):
        ini = _find_alembic_ini()
        assert ini is not None
        await _run_alembic(ini, _migration_env(url), "upgrade", "head")
        yield url


async def _pg_org(engine, name: str = "B10"):
    repo = OrgRepository(engine)
    return await repo.create_org(name, f"b10-{uuid.uuid4().hex[:10]}", plan=Plan.ENTERPRISE)


def _issue_kwargs(org_id: str, **extra):
    payload = '{"action_type":"tool"}'
    kw = dict(
        organization_id=org_id,
        principal_id="principal-1",
        agent_id="agent-1",
        identity_id="identity-1",
        intent="declared purpose",
        action_type="rai_trust_score",
        target="rai_trust_score",
        action_digest="d" * 64,
        canonical_action_payload=payload,
        approved_arguments={"text": "redacted"},
        idempotency_key=uuid.uuid4().hex,
        target_fingerprint="fp-1",
        caller_organization_id=org_id,
    )
    kw.update(extra)
    return kw


async def _ready_claim(kernel: Phase7AAuthorityKernel, org_id: str, worker: str = "worker-a"):
    issued = await kernel.issue(**_issue_kwargs(org_id))
    await kernel.acquire_lease(
        request_id=issued.request_id, worker_id=worker, organization_id=org_id
    )
    await kernel.admit(request_id=issued.request_id, worker_id=worker, organization_id=org_id)
    claim = await kernel.claim_backend_start(
        request_id=issued.request_id, worker_id=worker, organization_id=org_id
    )
    return issued, claim


def _http_client(app, token: str | None = None) -> httpx.AsyncClient:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url=ISSUER,
        headers=headers,
        follow_redirects=False,
    )


# ── mcp/server.py: missing and malformed auth ───────────────────────────────


class TestMcpMissingAndMalformedAuth:
    @pytest.mark.asyncio
    async def test_empty_bearer_token_is_unauthorized(self, mcp_oauth_app) -> None:
        app, *_ = mcp_oauth_app
        async with _http_client(app) as client:
            response = await client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
                headers={"Authorization": "Bearer   "},
            )
        assert response.status_code == 401
        assert response.json()["error"] == "unauthorized"

    @pytest.mark.asyncio
    async def test_wp_at_rejected_when_oauth_server_disabled(self, mcp_api_only_app) -> None:
        app, raw_key = mcp_api_only_app
        async with _http_client(app, "wp_at_not-configured") as client:
            oauthish = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
        async with _http_client(app, raw_key) as client:
            api_key = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
        assert oauthish.status_code == 401
        assert api_key.status_code != 401

    @pytest.mark.asyncio
    async def test_api_only_deployment_has_no_www_authenticate_oauth_hint(
        self, mcp_api_only_app
    ) -> None:
        app, _ = mcp_api_only_app
        async with _http_client(app) as client:
            response = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
        assert response.status_code == 401
        assert "www-authenticate" not in response.headers

    @pytest.mark.asyncio
    @pytest.mark.parametrize("path", ["/mcp", "/sse"])
    async def test_missing_auth_on_hosted_transports(self, mcp_oauth_app, path: str) -> None:
        app, *_ = mcp_oauth_app
        async with _http_client(app) as client:
            if path == "/mcp":
                response = await client.post(
                    path, json={"jsonrpc": "2.0", "id": 1, "method": "ping"}
                )
            else:
                response = await client.get(path)
        assert response.status_code == 401
        assert "resource_metadata=" in response.headers.get("www-authenticate", "")

    @pytest.mark.asyncio
    async def test_auth_failure_budget_returns_429(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import responsibleai.dashboard.config as config_module
        import responsibleai.db as db_module

        engine = create_engine(":memory:")
        await engine.init()
        monkeypatch.setattr(db_module, "create_engine", lambda _url: engine)
        monkeypatch.setenv("RAI_MCP_HTTP_AUTH_MAX_FAILURES", "2")
        monkeypatch.setattr(
            config_module,
            "get_settings",
            lambda: Settings(mcp_oauth_issuer=ISSUER, mcp_oauth_resource_uri=RESOURCE),
        )
        app = _build_http_app()
        async with LifespanManager(app) as manager:
            async with _http_client(manager.app, "not-a-real-key") as client:
                await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
                await client.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "ping"})
                blocked = await client.post(
                    "/mcp", json={"jsonrpc": "2.0", "id": 3, "method": "ping"}
                )
        assert blocked.status_code == 429
        assert blocked.json()["error"] == "too_many_attempts"

    @pytest.mark.asyncio
    async def test_demo_unauthenticated_mode_allows_health_only_shape(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import responsibleai.dashboard.config as config_module
        import responsibleai.db as db_module

        engine = create_engine(":memory:")
        await engine.init()
        monkeypatch.setattr(db_module, "create_engine", lambda _url: engine)
        monkeypatch.setattr(
            config_module,
            "get_settings",
            lambda: Settings(mcp_http_allow_unauthenticated_demo=True, mcp_oauth_issuer=""),
        )
        app = _build_http_app()
        async with LifespanManager(app) as manager:
            async with _http_client(manager.app) as client:
                response = await client.post(
                    "/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"}
                )
        assert response.status_code != 401


# ── mcp/server.py: malformed OAuth and transport errors ─────────────────────


class TestMcpOAuthMalformedAndEndpoints:
    @pytest.mark.asyncio
    async def test_oauth_register_requires_json_object(self, mcp_oauth_app) -> None:
        app, *_ = mcp_oauth_app
        async with _http_client(app) as client:
            response = await client.post("/oauth/register", json=["not", "an", "object"])
        assert response.status_code == 400
        assert response.json()["error"] == "invalid_client_metadata"

    @pytest.mark.asyncio
    async def test_oauth_register_rejects_oversized_content_length(self, mcp_oauth_app) -> None:
        app, *_ = mcp_oauth_app
        async with _http_client(app) as client:
            response = await client.post(
                "/oauth/register",
                content=b"{}",
                headers={"Content-Type": "application/json", "Content-Length": "99999"},
            )
        assert response.status_code == 413

    @pytest.mark.asyncio
    async def test_oauth_token_rejects_oversized_body(self, mcp_oauth_app) -> None:
        app, *_ = mcp_oauth_app
        async with _http_client(app) as client:
            response = await client.post(
                "/oauth/token",
                content=b"x" * 20_000,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        assert response.status_code == 413
        assert response.json()["error"] == "invalid_request"

    @pytest.mark.asyncio
    async def test_oauth_authorize_get_rejects_missing_client(self, mcp_oauth_app) -> None:
        app, *_ = mcp_oauth_app
        async with _http_client(app) as client:
            response = await client.get("/oauth/authorize", params={"response_type": "code"})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_oauth_authorize_post_invalid_utf8_form(self, mcp_oauth_app) -> None:
        app, *_ = mcp_oauth_app
        async with _http_client(app) as client:
            response = await client.post(
                "/oauth/authorize",
                content=b"\xff\xfe",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        assert response.status_code == 400
        assert response.json()["error"] == "invalid_request"

    @pytest.mark.asyncio
    async def test_oauth_token_invalid_grant_records_failure(self, mcp_oauth_app) -> None:
        app, *_ = mcp_oauth_app
        async with _http_client(app) as client:
            response = await client.post(
                "/oauth/token",
                data={"grant_type": "password", "username": "x", "password": "y"},
            )
        assert response.status_code == 400
        assert response.json()["error"] == "unsupported_grant_type"

    @pytest.mark.asyncio
    async def test_protected_resource_metadata_oidc_fallback(self, mcp_oidc_resource_app) -> None:
        app = mcp_oidc_resource_app
        async with _http_client(app) as client:
            response = await client.get("/.well-known/oauth-protected-resource")
        assert response.status_code == 200
        body = response.json()
        assert body["authorization_servers"] == ["https://idp.example"]
        assert body["resource"].endswith("/mcp")

    @pytest.mark.asyncio
    async def test_protected_resource_metadata_404_without_oauth_or_oidc(
        self, mcp_api_only_app
    ) -> None:
        app, _ = mcp_api_only_app
        async with _http_client(app) as client:
            response = await client.get("/.well-known/oauth-protected-resource")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_server_card_lists_oauth_when_authorization_server_enabled(
        self, mcp_oauth_app
    ) -> None:
        app, *_ = mcp_oauth_app
        async with _http_client(app) as client:
            response = await client.get("/.well-known/mcp/server-card.json")
        payload = response.json()
        assert payload["authentication"]["schemes"] == ["oauth2", "apiKey"]

    @pytest.mark.asyncio
    async def test_ready_returns_503_when_database_ping_fails(self, mcp_api_only_app) -> None:
        from responsibleai.db.engine import DatabaseEngine

        app, _ = mcp_api_only_app
        with patch.object(DatabaseEngine, "ping", new_callable=AsyncMock) as mock_ping:
            mock_ping.return_value = False
            async with _http_client(app) as client:
                response = await client.get("/ready")
        assert response.status_code == 503
        assert response.json()["database"] == "disconnected"

    @pytest.mark.asyncio
    async def test_openai_challenge_404_when_unconfigured(self, mcp_api_only_app) -> None:
        app, _ = mcp_api_only_app
        async with _http_client(app) as client:
            response = await client.get("/.well-known/openai-apps-challenge")
        assert response.status_code == 404


class TestMcpOAuthWrongTenantAndScope:
    @pytest.mark.asyncio
    async def test_oauth_token_wrong_resource_is_denied(self, mcp_oauth_app) -> None:
        app, *_ = mcp_oauth_app
        async with _http_client(app) as client:
            reg = await client.post(
                "/oauth/register",
                json={
                    "client_name": "Wrong Resource",
                    "redirect_uris": [REDIRECT],
                    "grant_types": ["authorization_code"],
                    "response_types": ["code"],
                    "token_endpoint_auth_method": "none",
                },
            )
            client_id = reg.json()["client_id"]
            _verifier, challenge = _pkce()
            start = await client.get(
                "/oauth/authorize",
                params={
                    "response_type": "code",
                    "client_id": client_id,
                    "redirect_uri": REDIRECT,
                    "scope": "whitepact:review",
                    "state": "s",
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                    "resource": "https://evil.example/mcp",
                },
            )
        assert start.status_code == 400

    @pytest.mark.asyncio
    async def test_with_oauth_security_decorates_tool_metadata(self) -> None:
        from responsibleai.mcp.tools import PRODUCTION_TOOL_DEFS

        tool = _with_oauth_security(PRODUCTION_TOOL_DEFS[0])
        assert tool.securitySchemes == [{"type": "oauth2", "scopes": ["whitepact:review"]}]
        assert tool.meta is not None
        assert tool.meta["securitySchemes"] == tool.securitySchemes


class TestAuthFailureLimiterBranches:
    @pytest.mark.asyncio
    async def test_limiter_prunes_expired_window(self) -> None:
        limiter = _AuthFailureLimiter(max_failures=2, window_seconds=0.01)
        await limiter.record_failure("cred:a")
        await asyncio.sleep(0.02)
        assert await limiter.is_blocked("cred:a") is False

    @pytest.mark.asyncio
    async def test_limiter_without_peer_key_skips_aggregate(self) -> None:
        limiter = _AuthFailureLimiter(max_failures=1, window_seconds=60.0, peer_max_failures=1)
        await limiter.record_failure("cred:only")
        assert await limiter.is_blocked("cred:only", peer_key=None) is True


# ── runtime/authority_kernel.py remaining branches ────────────────────────────


def test_is_deadlock_matches_serialization_phrases() -> None:
    assert _is_deadlock(OperationalError("serialization failure", None, object())) is True
    assert _is_deadlock(OperationalError("could not serialize access", None, object())) is True


@pytest.mark.asyncio
async def test_kernel_issue_requires_postgres() -> None:
    engine = create_engine(":memory:")
    await engine.init()
    kernel = Phase7AAuthorityKernel(engine)
    try:
        with pytest.raises(AuthorityDatabaseError, match="PostgreSQL"):
            await kernel.issue(**_issue_kwargs("missing-org"))
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_kernel_issue_unknown_organization(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        kernel = Phase7AAuthorityKernel(engine)
        with pytest.raises(AuthorityKernelError, match="Unknown organization"):
            await kernel.issue(**_issue_kwargs(uuid.uuid4().hex))
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_kernel_acquire_lease_cross_tenant(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org_a = await _pg_org(engine, "A")
        org_b = await _pg_org(engine, "B")
        kernel = Phase7AAuthorityKernel(engine)
        issued = await kernel.issue(**_issue_kwargs(org_a.id))
        with pytest.raises(CrossTenantAccessError):
            await kernel.acquire_lease(
                request_id=issued.request_id, worker_id="w1", organization_id=org_b.id
            )
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_kernel_acquire_lease_unknown_request(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _pg_org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        with pytest.raises(AuthorityKernelError, match="Unknown request"):
            await kernel.acquire_lease(
                request_id=uuid.uuid4().hex, worker_id="w1", organization_id=org.id
            )
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_kernel_claim_backend_cross_tenant(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org_a = await _pg_org(engine, "A")
        org_b = await _pg_org(engine, "B")
        kernel = Phase7AAuthorityKernel(engine)
        issued = await kernel.issue(**_issue_kwargs(org_a.id))
        await kernel.acquire_lease(
            request_id=issued.request_id, worker_id="w1", organization_id=org_a.id
        )
        await kernel.admit(request_id=issued.request_id, worker_id="w1", organization_id=org_a.id)
        with pytest.raises(CrossTenantAccessError):
            await kernel.claim_backend_start(
                request_id=issued.request_id, worker_id="w1", organization_id=org_b.id
            )
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_kernel_claim_backend_inactive_org(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _pg_org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        issued = await kernel.issue(**_issue_kwargs(org.id))
        await kernel.acquire_lease(
            request_id=issued.request_id, worker_id="w1", organization_id=org.id
        )
        await kernel.admit(request_id=issued.request_id, worker_id="w1", organization_id=org.id)
        await OrgRepository(engine).set_governance_status(org.id, GovernanceStatus.SUSPENDED)
        with pytest.raises(AuthorityKernelError, match="ACTIVE"):
            await kernel.claim_backend_start(
                request_id=issued.request_id, worker_id="w1", organization_id=org.id
            )
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_kernel_claim_backend_epoch_mismatch(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _pg_org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        issued = await kernel.issue(**_issue_kwargs(org.id))
        await kernel.acquire_lease(
            request_id=issued.request_id, worker_id="w1", organization_id=org.id
        )
        async with engine.raw.begin() as conn:
            await bump_epoch_on_connection(conn, org.id)
        with pytest.raises(AuthorizationIneligibleError, match="epoch"):
            await kernel.admit(request_id=issued.request_id, worker_id="w1", organization_id=org.id)
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_kernel_claim_backend_wrong_worker(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _pg_org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        issued = await kernel.issue(**_issue_kwargs(org.id))
        await kernel.acquire_lease(
            request_id=issued.request_id, worker_id="owner", organization_id=org.id
        )
        await kernel.admit(request_id=issued.request_id, worker_id="owner", organization_id=org.id)
        with pytest.raises(StaleWorkerError):
            await kernel.claim_backend_start(
                request_id=issued.request_id, worker_id="intruder", organization_id=org.id
            )
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_kernel_claim_backend_start_cas_lost(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _pg_org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        issued = await kernel.issue(**_issue_kwargs(org.id))
        await kernel.acquire_lease(
            request_id=issued.request_id, worker_id="w1", organization_id=org.id
        )
        await kernel.admit(request_id=issued.request_id, worker_id="w1", organization_id=org.id)

        async def claim():
            return await kernel.claim_backend_start(
                request_id=issued.request_id, worker_id="w1", organization_id=org.id
            )

        first, second = await asyncio.gather(claim(), claim(), return_exceptions=True)
        winners = [r for r in (first, second) if not isinstance(r, BaseException)]
        losers = [r for r in (first, second) if isinstance(r, BaseException)]
        assert len(winners) == 1
        assert len(losers) == 1
        assert isinstance(losers[0], AuthorityKernelError)
        assert str(losers[0]) in {
            "Backend-start CAS lost",
            "Attempt is not ADMITTED",
        }
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_kernel_admit_oneshot_nonce_double_consume(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _pg_org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        issued = await kernel.issue(**_issue_kwargs(org.id))
        await kernel.acquire_lease(
            request_id=issued.request_id, worker_id="w1", organization_id=org.id
        )
        async with engine.raw.begin() as conn:
            auth = (
                (await conn.execute(select(auths).where(auths.c.request_id == issued.request_id)))
                .mappings()
                .one()
            )
            await conn.execute(
                nonces.insert().values(
                    nonce=auth["oneshot_authority_id"],
                    authorization_id=auth["authorization_id"][:36],
                    organization_id=org.id,
                    consumed_at=datetime.now(UTC).isoformat(),
                )
            )
        with pytest.raises(AuthorizationIneligibleError, match="Oneshot"):
            await kernel.admit(request_id=issued.request_id, worker_id="w1", organization_id=org.id)
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_kernel_final_cas_wrong_attempt_state(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _pg_org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        _, claim = await _ready_claim(kernel, org.id)
        async with engine.raw.begin() as conn:
            await conn.execute(
                update(attempts)
                .where(attempts.c.attempt_id == claim.attempt_id)
                .values(state=AttemptState.RUNNING.value)
            )
        with pytest.raises(PreEffectCasRejected, match="BACKEND_STARTING"):
            await kernel.claim_local_effect_start(
                claim, action_digest=claim.action_digest, target_fingerprint="fp-1"
            )
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_kernel_final_cas_stale_fence_counter(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _pg_org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        _, claim = await _ready_claim(kernel, org.id)
        async with engine.raw.begin() as conn:
            await conn.execute(
                update(fences)
                .where(fences.c.request_id == claim.request_id)
                .values(current_generation=claim.lease_generation + 5)
            )
        with pytest.raises(PreEffectCasRejected, match="Fence"):
            await kernel.claim_local_effect_start(
                claim, action_digest=claim.action_digest, target_fingerprint="fp-1"
            )
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_kernel_mark_outbox_published_happy_path(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _pg_org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        await kernel.issue(**_issue_kwargs(org.id))
        row = await kernel.claim_outbox_row(publisher_id="pub-b10")
        assert row is not None
        ticket_id = uuid.uuid4().hex
        await kernel.mark_outbox_published(outbox_id=row["outbox_id"], queue_ticket_id=ticket_id)
        async with engine.raw.connect() as conn:
            status = (
                await conn.execute(
                    select(outbox.c.status, outbox.c.queue_ticket_id).where(
                        outbox.c.outbox_id == row["outbox_id"]
                    )
                )
            ).one()
        assert status.status == OutboxStatus.PUBLISHED.value
        assert status.queue_ticket_id == ticket_id
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_kernel_claim_outbox_reclaims_stale_publishing(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _pg_org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        await kernel.issue(**_issue_kwargs(org.id))
        first = await kernel.claim_outbox_row(publisher_id="pub-a")
        assert first is not None
        stale = datetime.now(UTC) - timedelta(minutes=5)
        async with engine.raw.begin() as conn:
            await conn.execute(
                update(outbox)
                .where(outbox.c.outbox_id == first["outbox_id"])
                .values(claimed_at=stale)
            )
        second = await kernel.claim_outbox_row(publisher_id="pub-b")
        assert second is not None
        assert second["outbox_id"] == first["outbox_id"]
    finally:
        await engine.close()


class _BoomCapacity:
    def reserve(self, **kwargs):
        raise RuntimeError("capacity backend down")


class _MemoryTransport:
    def enqueue(self, ticket: QueueTicket) -> None:
        _ = ticket


@pytest.mark.asyncio
async def test_kernel_publish_outbox_capacity_reserve_exception(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _pg_org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        await kernel.issue(**_issue_kwargs(org.id))
        with pytest.raises(AuthorityKernelError, match="capacity reservation"):
            await kernel.publish_outbox(
                publisher_id="pub-b10",
                transport=_MemoryTransport(),
                capacity_reserve=_BoomCapacity(),
            )
        async with engine.raw.connect() as conn:
            status = (
                await conn.execute(
                    select(outbox.c.status).where(outbox.c.organization_id == org.id)
                )
            ).scalar_one()
        assert status == OutboxStatus.PENDING.value
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_kernel_acquire_lease_after_admit_keeps_admitted_state(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _pg_org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        issued = await kernel.issue(**_issue_kwargs(org.id))
        await kernel.acquire_lease(
            request_id=issued.request_id, worker_id="w1", organization_id=org.id
        )
        await kernel.admit(request_id=issued.request_id, worker_id="w1", organization_id=org.id)
        lease = await kernel.acquire_lease(
            request_id=issued.request_id, worker_id="w2", organization_id=org.id
        )
        assert lease["worker_id"] == "w2"
        async with engine.raw.connect() as conn:
            state = (
                await conn.execute(
                    select(attempts.c.state).where(attempts.c.request_id == issued.request_id)
                )
            ).scalar_one()
        assert state == AttemptState.ADMITTED.value
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_kernel_final_cas_auth_not_consumed(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _pg_org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        issued, claim = await _ready_claim(kernel, org.id)
        async with engine.raw.begin() as conn:
            await conn.execute(
                update(auths)
                .where(auths.c.request_id == issued.request_id)
                .values(status=AuthorizationStatus.ISSUED.value, consumed_at=None)
            )
        with pytest.raises(PreEffectCasRejected, match="eligible"):
            await kernel.claim_local_effect_start(
                claim, action_digest=claim.action_digest, target_fingerprint="fp-1"
            )
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_kernel_load_request_success(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _pg_org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        issued = await kernel.issue(**_issue_kwargs(org.id))
        row = await kernel.load_request(issued.request_id, organization_id=org.id)
        assert row["request_id"] == issued.request_id
        assert row["organization_id"] == org.id
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_kernel_claim_local_with_stale_claim_digest(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _pg_org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        _, claim = await _ready_claim(kernel, org.id)
        stale = replace(claim, action_digest="e" * 64)
        with pytest.raises(PreEffectCasRejected, match="digest"):
            await kernel.claim_local_effect_start(
                stale, action_digest=stale.action_digest, target_fingerprint="fp-1"
            )
    finally:
        await engine.close()
