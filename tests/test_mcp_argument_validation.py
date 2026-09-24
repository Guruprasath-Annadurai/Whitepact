# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""MCP dispatch boundary validation (WP-V1-FIND-001)."""

from __future__ import annotations

import pytest
import respx

from responsibleai.mcp.tools import dispatch_tool


class TestRedteamAnalyzeValidation:
    async def test_string_instead_of_object_for_responses(self) -> None:
        result = await dispatch_tool(
            "rai_redteam_analyze",
            {"model_name": "m", "provider": "p", "responses": "not-an-object"},
        )
        assert result["error"] == "invalid_argument"
        assert result["field"] == "responses"

    async def test_list_instead_of_object(self) -> None:
        result = await dispatch_tool(
            "rai_redteam_analyze",
            {"model_name": "m", "provider": "p", "responses": []},
        )
        assert result["error"] == "invalid_argument"

    async def test_null_responses(self) -> None:
        result = await dispatch_tool(
            "rai_redteam_analyze",
            {"model_name": "m", "provider": "p", "responses": None},
        )
        assert result["error"] == "invalid_argument"

    async def test_valid_payload_regression(self) -> None:
        result = await dispatch_tool(
            "rai_redteam_analyze",
            {
                "model_name": "m",
                "provider": "p",
                "responses": {"prompt_injection": "refused"},
            },
        )
        assert "overall_security_score" in result or "findings" in result or "error" not in result


class TestBiasEvaluateValidation:
    async def test_probe_responses_must_be_object(self) -> None:
        result = await dispatch_tool(
            "rai_bias_evaluate",
            {"model_name": "m", "provider": "p", "probe_responses": "bad"},
        )
        assert result["error"] == "invalid_argument"
        assert result["field"] == "probe_responses"


class TestDriftCheckValidation:
    async def test_baseline_score_must_be_object(self) -> None:
        result = await dispatch_tool(
            "rai_drift_check",
            {
                "model_name": "m",
                "provider": "p",
                "baseline_score": "bad",
                "current_score": {"overall": 0.5},
            },
        )
        assert result["error"] == "invalid_argument"


class TestPolicyCheckValidation:
    async def test_policy_must_be_object(self) -> None:
        result = await dispatch_tool(
            "rai_policy_check",
            {"text": "hello", "policy": "not-a-policy"},
        )
        assert result["error"] == "invalid_argument"

    async def test_missing_required_text(self) -> None:
        result = await dispatch_tool("rai_policy_check", {"policy": {}})
        assert result["error"] == "invalid_argument"


class TestDispatchRootValidation:
    async def test_non_object_arguments(self) -> None:
        result = await dispatch_tool("rai_health", "string-args")  # type: ignore[arg-type]
        assert result["error"] == "invalid_argument"
        assert result["field"] == "arguments"


class TestTrustCheckFailClosed:
    @respx.mock
    async def test_provider_outage_does_not_pass(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from responsibleai.mcp.tools import _trust_client

        original = _trust_client.base_url
        _trust_client.base_url = "https://trust-validation.invalid"
        monkeypatch.delenv("WHITEPACT_TRUST_FAILURE_MODE", raising=False)
        try:
            import httpx

            respx.get("https://trust-validation.invalid/api/trust-index/check").mock(
                return_value=httpx.Response(503, json={"detail": "down"})
            )
            result = await dispatch_tool(
                "rai_check_trust", {"model_name": "m", "provider": "p"}
            )
            assert result["passes"] is False
            assert result["trust_status"] == "UNKNOWN"
            assert result["error"] is not None
        finally:
            _trust_client.base_url = original
