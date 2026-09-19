# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
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

import json

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
                read_stream,
                write_stream,
                _get_session_id,
            ),
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.list_tools()

        names = {t.name for t in result.tools}
        assert "rai_health" in names
        assert len(result.tools) == 30

    async def test_call_tool_over_streamable_http(self, seeded_app) -> None:
        app, raw_key = seeded_app
        async with (
            _asgi_http_client(app, raw_key) as http_client,
            streamable_http_client("/mcp", http_client=http_client) as (
                read_stream,
                write_stream,
                _get_session_id,
            ),
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool("rai_health", {})

        assert result.isError is not True
        # Structured tool-output contracts (spec 2025-06-18): the same
        # payload is available as structuredContent, not just serialized
        # into the legacy content[0].text blob.
        assert result.structuredContent is not None
        assert json.loads(result.content[0].text) == result.structuredContent

    async def test_openai_review_workflow_over_real_transport(self, seeded_app) -> None:
        """Exercise review inputs through the real MCP layer, not handler stubs."""
        app, raw_key = seeded_app
        calls = {
            "rai_health": {},
            "rai_scan": {
                "text": (
                    "Contact John at john@example.com or 555-123-4567. His employee ID is EMP-2048."
                ),
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
                "system_description": (
                    "An automated resume-screening system used by employers to rank "
                    "candidates and decide who proceeds to interviews."
                ),
                "deployment_sector": "employment",
                "affects_natural_persons": True,
                "is_fully_automated": True,
            },
            "rai_hallucination": {
                "source": "The project review meeting is scheduled for Tuesday at 3 PM.",
                "text": "The project review meeting is scheduled for Wednesday at 3 PM.",
            },
        }

        async with (
            _asgi_http_client(app, raw_key) as http_client,
            streamable_http_client("/mcp", http_client=http_client) as (
                read_stream,
                write_stream,
                _get_session_id,
            ),
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools = (await session.list_tools()).tools
                resources = (await session.list_resources()).resources
                results = {
                    name: await session.call_tool(name, arguments)
                    for name, arguments in calls.items()
                }

        assert len(tools) == 30
        assert len(resources) == 20
        assert all(
            tool.annotations is not None
            and tool.annotations.readOnlyHint is not None
            and tool.annotations.openWorldHint is not None
            and tool.annotations.destructiveHint is not None
            for tool in tools
        )
        assert all(result.isError is not True for result in results.values())

        payloads = {name: result.structuredContent for name, result in results.items()}
        assert payloads["rai_health"]["status"] == "ok"
        assert payloads["rai_health"]["tools"] == 30
        assert payloads["rai_scan"]["has_pii"] is True
        assert "john@example.com" not in payloads["rai_scan"]["redacted_text"]
        assert "555-123-4567" not in payloads["rai_scan"]["redacted_text"]
        assert isinstance(payloads["rai_trust_score"]["score"], float)
        assert isinstance(payloads["rai_trust_score"]["risk_tier"], str)
        assert payloads["rai_eu_ai_act_classify"]["risk_tier"] == "HIGH"
        assert payloads["rai_hallucination"]["source_contradiction_detected"] is True
        assert payloads["rai_hallucination"]["hallucination_detected"] is True


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
        assert payload["tools"] == 30


class TestMCPServerCard:
    """/.well-known/mcp/server-card.json — the static capability card
    directories (e.g. Smithery) fall back to when they can't complete a
    live authenticated scan against /mcp, since this deployment has no
    OAuth authorization server configured (only static Bearer API
    keys, which an automated crawler can't obtain)."""

    async def test_server_card_is_public_no_auth_required(self, seeded_app) -> None:
        app, _raw_key = seeded_app
        async with await _raw_client(app) as client:
            response = await client.get("/.well-known/mcp/server-card.json")
        assert response.status_code == 200

    async def test_server_card_matches_live_tool_and_resource_defs(self, seeded_app) -> None:
        from responsibleai import __version__
        from responsibleai.mcp.resources import RESOURCE_DEFS
        from responsibleai.mcp.tools import TOOL_DEFS

        app, _raw_key = seeded_app
        async with await _raw_client(app) as client:
            response = await client.get("/.well-known/mcp/server-card.json")
        payload = response.json()
        assert payload["serverInfo"] == {"name": "whitepact", "version": __version__}
        assert len(payload["tools"]) == len(TOOL_DEFS)
        assert {t["name"] for t in payload["tools"]} == {t.name for t in TOOL_DEFS}
        assert len(payload["resources"]) == len(RESOURCE_DEFS)
        assert payload["prompts"] == []
