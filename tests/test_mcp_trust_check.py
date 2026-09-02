"""Tests for the rai_check_trust MCP tool — the agent-native primitive
described in GAME_CHANGER_BUILD_PLAN.md Phase B. Unlike every other rai_*
tool, dispatch here makes an HTTP call (the MCP server is stateless and
has no direct DB access — see responsibleai/mcp/tools.py's module
docstring precedent in _handle_incident_log), so these tests mock that
call with respx rather than hitting a real DB fixture."""

from __future__ import annotations

import httpx
import pytest
import respx

from responsibleai.mcp.tools import TOOL_DEFS, _dispatch_tool_unchecked, _trust_client


@pytest.fixture(autouse=True)
def _pinned_base_url():
    original = _trust_client.base_url
    _trust_client.base_url = "https://test.invalid"
    yield
    _trust_client.base_url = original


class TestToolRegistration:
    def test_rai_check_trust_is_registered(self) -> None:
        names = {t.name for t in TOOL_DEFS}
        assert "rai_check_trust" in names

    def test_requires_model_name_and_provider(self) -> None:
        tool = next(t for t in TOOL_DEFS if t.name == "rai_check_trust")
        assert set(tool.inputSchema["required"]) == {"model_name", "provider"}


class TestDispatchCheckTrust:
    async def test_missing_args_returns_error(self) -> None:
        r = await _dispatch_tool_unchecked("rai_check_trust", {})
        assert "error" in r

    @respx.mock
    async def test_known_trustworthy_model_passes(self) -> None:
        respx.get("https://test.invalid/api/trust-index/check").mock(
            return_value=httpx.Response(
                200,
                json={
                    "model": "gpt-4o",
                    "provider": "openai",
                    "known": True,
                    "trust_score": {"overall": 92.0, "grade": "A"},
                    "certified": True,
                    "has_reported_incidents": False,
                    "passport_id": "p1",
                    "verify_url": "/api/trust-index/verify/p1",
                    "recent_incidents": [],
                },
            )
        )
        r = await _dispatch_tool_unchecked(
            "rai_check_trust", {"model_name": "gpt-4o", "provider": "openai", "min_score": 70}
        )
        assert r["known"] is True
        assert r["certified"] is True
        assert r["passes"] is True
        assert r["error"] is None

    @respx.mock
    async def test_low_score_fails_threshold(self) -> None:
        respx.get("https://test.invalid/api/trust-index/check").mock(
            return_value=httpx.Response(
                200,
                json={
                    "model": "sketchy-tool",
                    "provider": "unknown",
                    "known": True,
                    "trust_score": {"overall": 15.0, "grade": "F"},
                    "certified": False,
                    "has_reported_incidents": True,
                    "recent_incidents": [{"title": "leaked PII"}],
                },
            )
        )
        r = await _dispatch_tool_unchecked(
            "rai_check_trust",
            {"model_name": "sketchy-tool", "provider": "unknown", "min_score": 70},
        )
        assert r["passes"] is False
        assert r["has_reported_incidents"] is True

    @respx.mock
    async def test_unknown_model_defaults_to_passing_fail_open(self) -> None:
        respx.get("https://test.invalid/api/trust-index/check").mock(
            return_value=httpx.Response(
                200,
                json={
                    "model": "never-assessed",
                    "provider": "nobody",
                    "known": False,
                    "trust_score": None,
                    "certified": False,
                    "has_reported_incidents": False,
                },
            )
        )
        r = await _dispatch_tool_unchecked(
            "rai_check_trust", {"model_name": "never-assessed", "provider": "nobody"}
        )
        assert r["known"] is False
        assert r["passes"] is True

    @respx.mock
    async def test_network_error_fails_open_and_reports_error(self) -> None:
        respx.get("https://test.invalid/api/trust-index/check").mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        r = await _dispatch_tool_unchecked("rai_check_trust", {"model_name": "x", "provider": "y"})
        assert r["passes"] is True
        assert r["error"] is not None
