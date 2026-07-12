"""Tests for the MCP server's plan-gated tool dispatch — tier enforcement and quota metering.

These exercise `_call_tool` directly with the module's contextvars set, simulating
what the HTTP/SSE transport's `handle_sse` does per-request.
"""

from __future__ import annotations

import json

import pytest

from responsibleai.db.engine import create_engine
from responsibleai.db.mcp_usage_repository import McpUsageRepository
from responsibleai.mcp import server as mcp_server
from responsibleai.rbac.models import OrgContext, Plan, Role


@pytest.fixture()
async def db():
    engine = create_engine(":memory:")
    await engine.init()
    yield engine
    await engine.close()


@pytest.fixture()
async def usage_repo(db):
    return McpUsageRepository(db)


def _set_context(org_ctx: OrgContext | None, usage_repo=None):
    org_token = mcp_server._current_org.set(org_ctx)
    usage_token = mcp_server._current_usage_repo.set(usage_repo)
    return org_token, usage_token


def _reset_context(tokens):
    org_token, usage_token = tokens
    mcp_server._current_org.reset(org_token)
    mcp_server._current_usage_repo.reset(usage_token)


class TestStdioUnrestricted:
    async def test_no_context_allows_any_tool(self):
        """Self-hosted stdio has no org context — every tool is callable."""
        result = await mcp_server._call_tool("rai_health", {})
        payload = json.loads(result[0].text)
        assert "error" not in payload

    async def test_no_context_allows_enterprise_tool(self):
        result = await mcp_server._call_tool("rai_passport_generate", {
            "model_name": "gpt-4o", "provider": "openai",
            "trust_dimensions": {"fairness": 0.8},
        })
        payload = json.loads(result[0].text)
        assert "error" not in payload


class TestTierGating:
    async def test_free_plan_blocked_from_pro_tool(self, usage_repo):
        ctx = OrgContext(key_id="k1", role=Role.ANALYST, org_id="org-1", plan=Plan.FREE)
        tokens = _set_context(ctx, usage_repo)
        try:
            result = await mcp_server._call_tool("rai_bias_evaluate", {})
        finally:
            _reset_context(tokens)
        payload = json.loads(result[0].text)
        assert payload["error"] == "upgrade_required"

    async def test_free_plan_has_no_hosted_access_even_for_free_tools(self, usage_repo):
        """FREE plan means self-hosted stdio only — the hosted transport isn't
        included even for nominally free-tier tools. Quota is 0 by design."""
        ctx = OrgContext(key_id="k1", role=Role.ANALYST, org_id="org-1", plan=Plan.FREE)
        tokens = _set_context(ctx, usage_repo)
        try:
            result = await mcp_server._call_tool("rai_health", {})
        finally:
            _reset_context(tokens)
        payload = json.loads(result[0].text)
        assert payload["error"] == "hosted_access_unavailable"

    async def test_pro_plan_allowed_free_tool(self, usage_repo):
        ctx = OrgContext(key_id="k1", role=Role.ANALYST, org_id="org-1", plan=Plan.PRO)
        tokens = _set_context(ctx, usage_repo)
        try:
            result = await mcp_server._call_tool("rai_health", {})
        finally:
            _reset_context(tokens)
        payload = json.loads(result[0].text)
        assert "error" not in payload

    async def test_pro_plan_blocked_from_enterprise_tool(self, usage_repo):
        ctx = OrgContext(key_id="k1", role=Role.ANALYST, org_id="org-1", plan=Plan.PRO)
        tokens = _set_context(ctx, usage_repo)
        try:
            result = await mcp_server._call_tool("rai_executive_summary", {})
        finally:
            _reset_context(tokens)
        payload = json.loads(result[0].text)
        assert payload["error"] == "upgrade_required"

    async def test_enterprise_plan_allowed_all_tiers(self, usage_repo):
        ctx = OrgContext(key_id="k1", role=Role.ANALYST, org_id="org-1", plan=Plan.ENTERPRISE)
        tokens = _set_context(ctx, usage_repo)
        try:
            result = await mcp_server._call_tool("rai_bias_evaluate", {
                "model_name": "gpt-4o", "provider": "openai",
                "probe_responses": {"gender": ["a response", "b response"]},
            })
        finally:
            _reset_context(tokens)
        payload = json.loads(result[0].text)
        assert "error" not in payload

    async def test_blocked_call_is_metered(self, usage_repo):
        ctx = OrgContext(key_id="k1", role=Role.ANALYST, org_id="org-1", plan=Plan.FREE)
        tokens = _set_context(ctx, usage_repo)
        try:
            await mcp_server._call_tool("rai_bias_evaluate", {})
        finally:
            _reset_context(tokens)
        usage = await usage_repo.usage_this_month("org-1")
        assert usage["blocked_calls"] == 1

    async def test_allowed_call_is_metered(self, usage_repo):
        ctx = OrgContext(key_id="k1", role=Role.ANALYST, org_id="org-1", plan=Plan.PRO)
        tokens = _set_context(ctx, usage_repo)
        try:
            await mcp_server._call_tool("rai_health", {})
        finally:
            _reset_context(tokens)
        usage = await usage_repo.usage_this_month("org-1")
        assert usage["allowed_calls"] == 1


class TestQuotaEnforcement:
    async def test_pro_plan_blocked_when_quota_exceeded(self, usage_repo, monkeypatch):
        monkeypatch.setattr(mcp_server, "monthly_quota", lambda plan: 2)
        ctx = OrgContext(key_id="k1", role=Role.ANALYST, org_id="org-1", plan=Plan.PRO)
        tokens = _set_context(ctx, usage_repo)
        try:
            await mcp_server._call_tool("rai_health", {})
            await mcp_server._call_tool("rai_health", {})
            result = await mcp_server._call_tool("rai_health", {})
        finally:
            _reset_context(tokens)
        payload = json.loads(result[0].text)
        assert payload["error"] == "quota_exceeded"

    async def test_enterprise_plan_unlimited_quota(self, usage_repo, monkeypatch):
        monkeypatch.setattr(mcp_server, "monthly_quota", lambda plan: None if plan == Plan.ENTERPRISE else 1)
        ctx = OrgContext(key_id="k1", role=Role.ANALYST, org_id="org-1", plan=Plan.ENTERPRISE)
        tokens = _set_context(ctx, usage_repo)
        try:
            for _ in range(5):
                result = await mcp_server._call_tool("rai_health", {})
        finally:
            _reset_context(tokens)
        payload = json.loads(result[0].text)
        assert "error" not in payload

    async def test_quota_exceeded_call_is_metered_as_blocked(self, usage_repo, monkeypatch):
        monkeypatch.setattr(mcp_server, "monthly_quota", lambda plan: 1)
        ctx = OrgContext(key_id="k1", role=Role.ANALYST, org_id="org-1", plan=Plan.PRO)
        tokens = _set_context(ctx, usage_repo)
        try:
            await mcp_server._call_tool("rai_health", {})
            await mcp_server._call_tool("rai_health", {})
        finally:
            _reset_context(tokens)
        usage = await usage_repo.usage_this_month("org-1")
        assert usage["allowed_calls"] == 1
        assert usage["blocked_calls"] == 1

    async def test_no_usage_repo_skips_quota_check(self):
        """When usage_repo isn't wired (e.g. mid-migration), tools still work — fail open, not closed."""
        ctx = OrgContext(key_id="k1", role=Role.ANALYST, org_id="org-1", plan=Plan.PRO)
        tokens = _set_context(ctx, usage_repo=None)
        try:
            result = await mcp_server._call_tool("rai_health", {})
        finally:
            _reset_context(tokens)
        payload = json.loads(result[0].text)
        assert "error" not in payload

    async def test_context_without_org_id_skips_metering(self, usage_repo):
        """Legacy/anon contexts (org_id=None) aren't metered — nothing to bill."""
        ctx = OrgContext(key_id="legacy", role=Role.OWNER, org_id=None, is_legacy=True)
        tokens = _set_context(ctx, usage_repo)
        try:
            result = await mcp_server._call_tool("rai_health", {})
        finally:
            _reset_context(tokens)
        payload = json.loads(result[0].text)
        assert "error" not in payload
