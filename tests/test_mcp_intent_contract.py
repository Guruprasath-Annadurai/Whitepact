# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real MCP protocol round-trip test proving Intent Contract wiring
end-to-end: an agent declares a contract via `IntentContractRepository`
(the same repo `POST /api/governance/intent-contracts` writes through),
then a subsequent governed MCP tool call that violates it is denied
before dispatch, exactly like `TestOrgAuthorityCeiling` in
test_mcp_governance_dispatch.py proves for org ceilings -- same
`governed_app` fixture pattern.
"""

from __future__ import annotations

import json

import httpx
import pytest
from asgi_lifespan import LifespanManager
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from responsibleai.db import IntentContractRepository, OrgRepository, create_engine
from responsibleai.governance.intent import build_intent_contract
from responsibleai.rbac.models import Plan, Role


@pytest.fixture()
async def governed_app(monkeypatch: pytest.MonkeyPatch):
    import responsibleai.db as db_module
    from responsibleai.dashboard.config import get_settings
    from responsibleai.mcp.server import _build_http_app

    settings = get_settings()
    monkeypatch.setattr(settings, "mcp_governance_enabled", True)

    engine = create_engine(":memory:")
    await engine.init()
    monkeypatch.setattr(db_module, "create_engine", lambda _url: engine)

    org_repo = OrgRepository(engine)
    org = await org_repo.create_org("Intent Test Co", "intent-test-co", plan=Plan.ENTERPRISE)
    key_rec, raw_key = await org_repo.create_key(org.id, "test-key", role=Role.ANALYST)

    app = _build_http_app()
    async with LifespanManager(app) as manager:
        yield manager.app, raw_key, org.id, key_rec.id, engine

    await engine.close()


def _client(app, raw_key: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": f"Bearer {raw_key}"},
    )


async def _call(app, raw_key: str, tool_name: str, arguments: dict):
    async with (
        _client(app, raw_key) as http_client,
        streamable_http_client("/mcp", http_client=http_client) as (
            read_stream,
            write_stream,
            _get_session_id,
        ),
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            return await session.call_tool(tool_name, arguments)


class TestIntentContractOnGovernedDispatch:
    async def test_call_within_declared_intent_proceeds(self, governed_app) -> None:
        app, raw_key, org_id, agent_id, engine = governed_app
        contract = build_intent_contract(
            org_id, agent_id, "run health checks", allowed_action_types=["rai_health"]
        )
        await IntentContractRepository(engine).declare(contract)

        result = await _call(app, raw_key, "rai_health", {})
        assert result.isError is not True
        payload = json.loads(result.content[0].text)
        assert "error" not in payload

    async def test_call_outside_declared_intent_denied(self, governed_app) -> None:
        app, raw_key, org_id, agent_id, engine = governed_app
        contract = build_intent_contract(
            org_id, agent_id, "run health checks only", allowed_action_types=["rai_health"]
        )
        await IntentContractRepository(engine).declare(contract)

        result = await _call(app, raw_key, "rai_scan", {"text": "hello"})
        assert result.isError is not True
        payload = json.loads(result.content[0].text)
        assert payload["error"] == "governance_denied"
        assert any(r.startswith("INTENT_VIOLATED") for r in payload["reason_codes"])

    async def test_no_declared_intent_behaves_as_before(self, governed_app) -> None:
        app, raw_key, _org_id, _agent_id, _engine = governed_app
        result = await _call(app, raw_key, "rai_scan", {"text": "hello"})
        assert result.isError is not True
        payload = json.loads(result.content[0].text)
        assert "error" not in payload

    async def test_expired_intent_no_longer_enforced(self, governed_app) -> None:
        from datetime import UTC, datetime, timedelta

        app, raw_key, org_id, agent_id, engine = governed_app
        expired = build_intent_contract(
            org_id,
            agent_id,
            "old task",
            allowed_action_types=["rai_health"],
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        )
        await IntentContractRepository(engine).declare(expired)

        result = await _call(app, raw_key, "rai_scan", {"text": "hello"})
        assert result.isError is not True
        payload = json.loads(result.content[0].text)
        assert "error" not in payload
