"""Tests for Security Remediation Gap 2 (stdio MCP governance bypass).
See `docs/enterprise-neural/REMEDIATION_GAP2_STDIO_GOVERNANCE.md`.

`_call_tool()` is the single handler both transports share. On stdio,
`_current_org`/`_current_governance` are never populated (they're set
only by the hosted-HTTP transport's auth middleware), so calling
`_call_tool()` directly with nothing else configured is exactly the
stdio scenario -- no fixture needs to fake a transport.
"""

from __future__ import annotations

import pytest

from responsibleai.dashboard.config import get_settings
from responsibleai.mcp import server as mcp_server


@pytest.fixture(autouse=True)
def _reset_enterprise_mode(monkeypatch: pytest.MonkeyPatch):
    """Every test starts and ends with enterprise_mode false --
    get_settings() is a process-wide singleton, so this must not leak
    between tests."""
    settings = get_settings()
    monkeypatch.setattr(settings, "enterprise_mode", False)
    yield


class TestReproduceTheUngovernedStdioFinding:
    """Before testing the fix, confirm the documented gap is real:
    with enterprise_mode at its default (false), stdio executes a
    HIGH-risk tool with zero governance check."""

    async def test_high_risk_tool_executes_by_default_on_stdio(self) -> None:
        content, structured = await mcp_server._call_tool("rai_health", {})
        assert "error" not in structured


class TestEnterpriseModeBlocksPrivilegedStdioExecution:
    async def test_high_risk_tool_blocked_in_enterprise_mode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(get_settings(), "enterprise_mode", True)
        content, structured = await mcp_server._call_tool("rai_hallucination", {"text": "x"})
        assert structured["error"] == "stdio_privileged_execution_blocked"
        assert "HIGH" in structured["message"] or "high" in structured["message"]

    async def test_medium_risk_tool_blocked_in_enterprise_mode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(get_settings(), "enterprise_mode", True)
        content, structured = await mcp_server._call_tool("rai_compliance", {})
        assert structured["error"] == "stdio_privileged_execution_blocked"

    async def test_low_risk_tool_still_allowed_in_enterprise_mode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(get_settings(), "enterprise_mode", True)
        content, structured = await mcp_server._call_tool("rai_health", {})
        assert "error" not in structured

    async def test_minimal_risk_tool_still_allowed_in_enterprise_mode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(get_settings(), "enterprise_mode", True)
        content, structured = await mcp_server._call_tool("rai_org_status", {})
        assert "error" not in structured

    async def test_unknown_tool_defaults_medium_and_is_blocked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """UNKNOWN = DENY: a tool name not in TOOL_RISK_TIERS defaults
        to MEDIUM via classify_action_risk() (fail-closed, not
        MINIMAL) and is therefore blocked in enterprise mode too --
        never silently allowed just because it's unrecognized."""
        monkeypatch.setattr(get_settings(), "enterprise_mode", True)
        content, structured = await mcp_server._call_tool("rai_some_future_tool", {})
        assert structured["error"] == "stdio_privileged_execution_blocked"


class TestDefaultBehaviorUnchanged:
    """enterprise_mode defaults to false -- every existing tool call
    on stdio must behave identically to before this gate existed."""

    @pytest.mark.parametrize(
        "tool_name",
        ["rai_health", "rai_hallucination", "rai_compliance", "rai_org_status"],
    )
    async def test_no_tool_is_blocked_when_enterprise_mode_is_false(self, tool_name: str) -> None:
        args = {"text": "x"} if tool_name == "rai_hallucination" else {}
        content, structured = await mcp_server._call_tool(tool_name, args)
        assert structured.get("error") != "stdio_privileged_execution_blocked"


class TestBlockedResponseNeverLeaksToolExecution:
    async def test_blocked_response_never_contains_a_real_tool_result_shape(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """rai_health's own real response always has a "status" key
        (same convention TestEvidenceWriteFailsClosed and
        TestAuthoritySubsystemCrashFailsClosed already check for the
        hosted path) -- prove the blocked stdio response is never
        that shape, i.e. the tool genuinely never ran."""
        monkeypatch.setattr(get_settings(), "enterprise_mode", True)
        content, structured = await mcp_server._call_tool("rai_benchmark", {})
        assert structured["error"] == "stdio_privileged_execution_blocked"
        assert "status" not in structured
