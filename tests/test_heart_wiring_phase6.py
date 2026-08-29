"""Tests for Heart Production Integration Phase 6 — wiring the Authority
Resolver (Phase 5) and the OIDC subject classifier into the live
decision path. See docs/heart-production/06_PHASE6_LIVE_WIRING.md.

Both wirings are opt-in and default-off:
- The OIDC classifier only elevates `IdentityKind.OIDC` to `HUMAN` when
  `Settings.oidc_human_indicator_claim` is configured AND the token's
  claim actually matches.
- The Heart legitimacy gate only denies anything when
  `Settings.enterprise_mode` is true AND a `root_authority_repo` is
  wired (always true once `mcp_governance_enabled` is on, per
  `_build_http_app()`).

This file proves, end-to-end through a real hosted MCP app (not just
the resolver/classifier in isolation, which `test_authority_resolver.py`
and `test_oidc_subject_classifier.py` already cover): the default
(both features off) is byte-for-byte unchanged, the gate correctly
denies a non-terminal identity once turned on, the gate still allows a
terminal (static-API-key) identity even when turned on, and the OIDC
classifier's HUMAN elevation makes an otherwise-non-terminal OIDC
identity pass the gate.
"""

from __future__ import annotations

import base64
import json
import secrets

import httpx
import pytest
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
    """Same fixture shape as test_mcp_oauth.py's `mcp_app` -- duplicated,
    not imported, matching this codebase's own "one independently
    deletable file" test convention. `await build(**settings_kwargs)`
    constructs a fresh hosted-MCP app with `mcp_governance_enabled=True`
    always on, plus whatever else the caller passes (enterprise_mode,
    oidc_human_indicator_claim, ...)."""
    import responsibleai.dashboard.config as config_module
    import responsibleai.db as db_module
    from responsibleai.mcp.server import _build_http_app

    engine = create_engine(":memory:")
    await engine.init()
    monkeypatch.setattr(db_module, "create_engine", lambda _url: engine)

    org_repo = OrgRepository(engine)
    org = await org_repo.create_org("Acme", "acme", plan=Plan.ENTERPRISE)
    _key_rec, raw_key = await org_repo.create_key(org.id, "test-key", role=Role.ANALYST)

    from asgi_lifespan import LifespanManager

    built = []

    async def _build(**settings_kwargs):
        # enterprise_mode=True also requires a crypto_root_key (Gap 1's
        # own fail-closed activation) -- supply one whenever the caller
        # is turning enterprise_mode on, unrelated to this file's own
        # Heart-gate concern but a real dependency of exercising it.
        if settings_kwargs.get("enterprise_mode"):
            settings_kwargs.setdefault("crypto_root_key", secrets.token_hex(32))
        settings = Settings(
            mcp_governance_enabled=True,
            oidc_issuer="https://idp.example.com",
            oidc_skip_verification=True,
            **settings_kwargs,
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


def _client(app, token: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": f"Bearer {token}"},
    )


async def _call_tool(app, token: str, tool_name: str, arguments: dict):
    async with (
        _client(app, token) as http_client,
        streamable_http_client("/mcp", http_client=http_client) as (
            read_stream,
            write_stream,
            _get_session_id,
        ),
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            return await session.call_tool(tool_name, arguments)


class TestHeartGateOffByDefault:
    """enterprise_mode defaults to False -- the Heart legitimacy check
    must be a complete no-op, identical to before Phase 6 existed, for
    both a static-API-key identity and a non-terminal OIDC identity."""

    async def test_oidc_identity_with_no_root_source_still_allowed(self, mcp_app) -> None:
        build, org_id, _raw_key = mcp_app
        app = await build()  # enterprise_mode defaults False
        token = _make_jwt({"sub": "user-1", "org_id": org_id, "roles": ["ANALYST"]})
        result = await _call_tool(app, token, "rai_health", {})
        payload = json.loads(result.content[0].text)
        assert "status" in payload  # the real rai_health payload, not a denial


class TestHeartGateDeniesNonTerminalIdentityWhenEnabled:
    async def test_oidc_identity_with_no_root_source_is_denied(self, mcp_app) -> None:
        """kind=OIDC (no oidc_human_indicator_claim configured) maps to
        RootType.WORKLOAD_IDENTITY, non-terminal, and this identity has
        no authority_source -- validate_root_chain() reports
        ROOT_TYPE_CANNOT_SELF_ORIGINATE, which must propagate through
        to an actual DENY once enterprise_mode is on."""
        build, org_id, _raw_key = mcp_app
        app = await build(enterprise_mode=True)
        token = _make_jwt({"sub": "user-1", "org_id": org_id, "roles": ["ANALYST"]})
        result = await _call_tool(app, token, "rai_health", {})
        payload = json.loads(result.content[0].text)
        assert payload["error"] == "governance_denied"
        assert any(code.startswith("HEART_LEGITIMACY_FAILED") for code in payload["reason_codes"])
        assert "status" not in payload  # the tool never actually ran


class TestHeartGateAllowsTerminalIdentityWhenEnabled:
    async def test_static_api_key_identity_still_allowed(self, mcp_app) -> None:
        """kind=ORGANIZATION (a static API key) maps to RootType.ORGANIZATION,
        terminal -- no authority_source needed, so the gate must still
        allow this, the common/default case, even with enterprise_mode
        on. Proves the gate doesn't break ordinary API-key auth."""
        build, _org_id, raw_key = mcp_app
        app = await build(enterprise_mode=True)
        result = await _call_tool(app, raw_key, "rai_health", {})
        payload = json.loads(result.content[0].text)
        assert "status" in payload
        assert "error" not in payload


class TestOidcHumanClassificationElevatesToTerminal:
    async def test_configured_amr_claim_makes_the_gate_pass(self, mcp_app) -> None:
        """With oidc_human_indicator_claim configured and a matching
        amr claim on the token, the identity classifies as HUMAN
        (terminal) instead of OIDC (non-terminal) -- the same
        no-root-source call that TestHeartGateDeniesNonTerminalIdentityWhenEnabled
        proves gets denied must now be allowed."""
        build, org_id, _raw_key = mcp_app
        app = await build(
            enterprise_mode=True,
            oidc_human_indicator_claim="amr",
            oidc_human_indicator_values=["pwd", "mfa"],
        )
        token = _make_jwt(
            {"sub": "user-2", "org_id": org_id, "roles": ["ANALYST"], "amr": ["pwd", "mfa"]}
        )
        result = await _call_tool(app, token, "rai_health", {})
        payload = json.loads(result.content[0].text)
        assert "status" in payload
        assert "error" not in payload

    async def test_non_matching_amr_value_stays_denied(self, mcp_app) -> None:
        """The classifier's own fail-safe: a configured claim that's
        present but doesn't match any indicator value must NOT elevate
        to HUMAN -- the gate must still deny."""
        build, org_id, _raw_key = mcp_app
        app = await build(
            enterprise_mode=True,
            oidc_human_indicator_claim="amr",
            oidc_human_indicator_values=["pwd", "mfa"],
        )
        token = _make_jwt(
            {
                "sub": "user-3",
                "org_id": org_id,
                "roles": ["ANALYST"],
                "amr": ["client_credentials"],
            }
        )
        result = await _call_tool(app, token, "rai_health", {})
        payload = json.loads(result.content[0].text)
        assert payload["error"] == "governance_denied"
        assert any(code.startswith("HEART_LEGITIMACY_FAILED") for code in payload["reason_codes"])
