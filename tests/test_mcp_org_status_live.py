"""Tests for `rai_org_status`'s live-org wiring (real follow-up to the
finding in compliance/OPENAI_PLUGIN_SUBMISSION_PREP.md's TC-P5 write-up
and tests/openai_review/review_contract.py): on the hosted MCP
transport with an authenticated caller, the tool now returns the real
org_id/plan/usage-quota state, not just a caller-supplied rollup.

Real MCP protocol round trips, same pattern as
tests/test_mcp_governance_dispatch.py / tests/test_mcp_intent_contract.py
-- proving the wiring works through the actual dispatch path, not just
in `_handle_org_status()` in isolation.
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
async def hosted_app(monkeypatch: pytest.MonkeyPatch):
    import responsibleai.db as db_module
    from responsibleai.mcp.server import _build_http_app

    engine = create_engine(":memory:")
    await engine.init()
    monkeypatch.setattr(db_module, "create_engine", lambda _url: engine)

    org_repo = OrgRepository(engine)
    # rai_org_status is an ENTERPRISE_TOOLS-tier tool (mcp/licensing.py)
    # -- a lower plan is rejected with "upgrade_required" before ever
    # reaching the handler, which would make every test here fail for
    # a reason unrelated to what's being tested.
    org = await org_repo.create_org(
        "Org Status Test Co", "org-status-test-co", plan=Plan.ENTERPRISE
    )
    _key_rec, raw_key = await org_repo.create_key(org.id, "test-key", role=Role.ANALYST)

    app = _build_http_app()
    async with LifespanManager(app) as manager:
        yield manager.app, raw_key, org.id, engine

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


class TestAuthenticatedCallerGetsRealOrgData:
    async def test_returns_real_org_id_and_plan(self, hosted_app) -> None:
        app, raw_key, org_id, _engine = hosted_app
        result = await _call(app, raw_key, "rai_org_status", {})
        payload = json.loads(result.content[0].text)
        assert payload["org_id"] == org_id
        assert payload["plan"] == "ENTERPRISE"

    async def test_usage_reflects_real_call_count(self, hosted_app) -> None:
        app, raw_key, org_id, engine = hosted_app
        # Two prior calls to any tool before the org_status call itself.
        await _call(app, raw_key, "rai_health", {})
        await _call(app, raw_key, "rai_health", {})
        result = await _call(app, raw_key, "rai_org_status", {})
        payload = json.loads(result.content[0].text)
        # 2 prior calls + this org_status call itself = 3.
        assert payload["usage"]["calls_this_month"] == 3

    async def test_caller_supplied_metrics_still_merged_in(self, hosted_app) -> None:
        """The real org fields are additive -- caller-supplied
        governance metrics (model grades etc.) still work exactly as
        before, merged alongside the real org_id/plan/usage."""
        app, raw_key, org_id, _engine = hosted_app
        result = await _call(
            app,
            raw_key,
            "rai_org_status",
            {"model_grades": {"gpt-4o": "A"}, "open_incidents": 1},
        )
        payload = json.loads(result.content[0].text)
        assert payload["org_id"] == org_id
        assert payload["models"]["grade_distribution"]["A"] == 1
        assert payload["operations"]["open_incidents"] == 1

    async def test_quota_status_matches_licensing_module(self, hosted_app) -> None:
        app, raw_key, _org_id, _engine = hosted_app
        # Assert the tool reports whatever the licensing module says for
        # this org's real plan, not a guess baked into the test.
        from responsibleai.mcp.licensing import monthly_quota

        expected_quota = monthly_quota(Plan.ENTERPRISE)
        result = await _call(app, raw_key, "rai_org_status", {})
        payload = json.loads(result.content[0].text)
        assert payload["usage"]["monthly_quota"] == expected_quota
        assert payload["usage"]["quota_status"] == ("UNLIMITED" if expected_quota is None else "OK")


class TestStdioHasNoRealOrgData:
    async def test_dispatch_tool_direct_call_with_no_context_has_no_org_fields(self) -> None:
        """The self-hosted stdio path (or any direct dispatch_tool()
        call outside a request context) has genuinely no org to look
        up -- org_id/plan/usage must be absent, not fabricated as
        None-filled placeholders that look like real (empty) data."""
        from responsibleai.mcp.tools import dispatch_tool

        result = await dispatch_tool("rai_org_status", {})
        assert "org_id" not in result
        assert "plan" not in result
        assert "usage" not in result
        # The caller-supplied rollup still works exactly as before.
        assert result["health_status"] == "HEALTHY"
