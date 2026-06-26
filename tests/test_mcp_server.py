"""Tests for the ResponsibleAI MCP server — tools, resources, and dispatch."""

from __future__ import annotations

import pytest

# ── Tool listing ───────────────────────────────────────────────────────────────

class TestMCPToolDefs:
    def test_tool_count(self) -> None:
        from responsibleai.mcp.tools import TOOL_DEFS
        assert len(TOOL_DEFS) == 10

    def test_all_tools_have_name_and_description(self) -> None:
        from responsibleai.mcp.tools import TOOL_DEFS
        for tool in TOOL_DEFS:
            assert tool.name
            assert tool.description

    def test_all_tools_have_input_schema(self) -> None:
        from responsibleai.mcp.tools import TOOL_DEFS
        for tool in TOOL_DEFS:
            assert tool.inputSchema is not None
            assert tool.inputSchema.get("type") == "object"

    def test_expected_tool_names(self) -> None:
        from responsibleai.mcp.tools import TOOL_DEFS
        names = {t.name for t in TOOL_DEFS}
        expected = {
            "rai_scan", "rai_trust_score", "rai_compliance", "rai_hallucination",
            "rai_cost_estimate", "rai_redteam_payloads", "rai_redteam_analyze",
            "rai_compare_models", "rai_audit_summary", "rai_health",
        }
        assert expected == names


# ── Resource listing ───────────────────────────────────────────────────────────

class TestMCPResourceDefs:
    def test_resource_count(self) -> None:
        from responsibleai.mcp.resources import RESOURCE_DEFS
        assert len(RESOURCE_DEFS) == 5

    def test_all_resources_have_uri_and_name(self) -> None:
        from responsibleai.mcp.resources import RESOURCE_DEFS
        for res in RESOURCE_DEFS:
            assert res.uri
            assert res.name

    def test_all_resources_json_mime(self) -> None:
        from responsibleai.mcp.resources import RESOURCE_DEFS
        for res in RESOURCE_DEFS:
            assert res.mimeType == "application/json"


# ── Tool handlers ──────────────────────────────────────────────────────────────

class TestRaiScan:
    @pytest.mark.asyncio
    async def test_clean_text_not_blocked(self) -> None:
        from responsibleai.mcp.tools import dispatch_tool
        r = await dispatch_tool("rai_scan", {"text": "Hello, world!"})
        assert r["is_blocked"] is False
        assert r["pii_findings"] == []

    @pytest.mark.asyncio
    async def test_email_detected(self) -> None:
        from responsibleai.mcp.tools import dispatch_tool
        r = await dispatch_tool("rai_scan", {"text": "Contact me at test@example.com"})
        assert r["has_pii"] is True
        cats = [f["category"] for f in r["pii_findings"]]
        assert "email" in cats

    @pytest.mark.asyncio
    async def test_redacted_text_returned_by_default(self) -> None:
        from responsibleai.mcp.tools import dispatch_tool
        r = await dispatch_tool("rai_scan", {"text": "My email is foo@bar.com"})
        assert r["redacted_text"] is not None

    @pytest.mark.asyncio
    async def test_no_redaction_when_disabled(self) -> None:
        from responsibleai.mcp.tools import dispatch_tool
        r = await dispatch_tool("rai_scan", {"text": "foo@bar.com", "redact": False})
        assert r["redacted_text"] is None


class TestRaiTrustScore:
    @pytest.mark.asyncio
    async def test_default_score_is_50(self) -> None:
        from responsibleai.mcp.tools import dispatch_tool
        r = await dispatch_tool("rai_trust_score", {})
        assert r["trust_score"] == 50.0
        assert r["grade"] == "F"

    @pytest.mark.asyncio
    async def test_perfect_score(self) -> None:
        from responsibleai.mcp.tools import dispatch_tool
        dims = {d: 1.0 for d in ["fairness", "privacy", "security", "robustness", "compliance", "authenticity"]}
        r = await dispatch_tool("rai_trust_score", dims)
        assert r["trust_score"] == 100.0
        assert r["grade"] == "A"
        assert r["risk"] == "LOW"

    @pytest.mark.asyncio
    async def test_score_has_dimensions(self) -> None:
        from responsibleai.mcp.tools import dispatch_tool
        r = await dispatch_tool("rai_trust_score", {"fairness": 0.8})
        assert "dimensions" in r
        assert "fairness" in r["dimensions"]


class TestRaiCompliance:
    @pytest.mark.asyncio
    async def test_returns_compliance_score(self) -> None:
        from responsibleai.mcp.tools import dispatch_tool
        r = await dispatch_tool("rai_compliance", {"framework": "NIST_AI_RMF"})
        assert "compliance_score" in r

    @pytest.mark.asyncio
    async def test_eu_ai_act_framework(self) -> None:
        from responsibleai.mcp.tools import dispatch_tool
        r = await dispatch_tool("rai_compliance", {"framework": "EU_AI_ACT", "use_case": "credit scoring"})
        assert "compliance_score" in r

    @pytest.mark.asyncio
    async def test_invalid_framework_falls_back(self) -> None:
        from responsibleai.mcp.tools import dispatch_tool
        r = await dispatch_tool("rai_compliance", {"framework": "UNKNOWN_XYZ"})
        assert "compliance_score" in r


class TestRaiHallucination:
    @pytest.mark.asyncio
    async def test_returns_risk_fields(self) -> None:
        from responsibleai.mcp.tools import dispatch_tool
        r = await dispatch_tool("rai_hallucination", {"text": "The capital of France is Paris."})
        assert "hallucination_risk" in r
        assert "risk_level" in r
        assert "consistency_score" in r
        assert "hedging_score" in r

    @pytest.mark.asyncio
    async def test_hedging_text_has_higher_risk(self) -> None:
        from responsibleai.mcp.tools import dispatch_tool
        hedged = "I think maybe possibly the answer might be around 42, but I'm not sure."
        r = await dispatch_tool("rai_hallucination", {"text": hedged})
        assert r["hedging_score"] > 0


class TestRaiCostEstimate:
    @pytest.mark.asyncio
    async def test_known_model_returns_cost(self) -> None:
        from responsibleai.mcp.tools import dispatch_tool
        r = await dispatch_tool("rai_cost_estimate", {
            "model": "gpt-4o",
            "provider": "openai",
            "input_tokens": 1000,
            "output_tokens": 500,
        })
        assert "total_cost_usd" in r
        assert r["total_cost_usd"] > 0

    @pytest.mark.asyncio
    async def test_local_model_is_free(self) -> None:
        from responsibleai.mcp.tools import dispatch_tool
        r = await dispatch_tool("rai_cost_estimate", {
            "model": "llama3.2",
            "provider": "ollama",
            "input_tokens": 10000,
            "output_tokens": 5000,
        })
        assert r["total_cost_usd"] == 0.0

    @pytest.mark.asyncio
    async def test_zero_tokens_is_zero(self) -> None:
        from responsibleai.mcp.tools import dispatch_tool
        r = await dispatch_tool("rai_cost_estimate", {
            "model": "gpt-4o", "provider": "openai",
            "input_tokens": 0, "output_tokens": 0,
        })
        assert r["total_cost_usd"] == 0.0


class TestRaiRedteam:
    @pytest.mark.asyncio
    async def test_payloads_returns_list(self) -> None:
        from responsibleai.mcp.tools import dispatch_tool
        r = await dispatch_tool("rai_redteam_payloads", {})
        assert r["count"] > 0
        assert len(r["payloads"]) == r["count"]

    @pytest.mark.asyncio
    async def test_filter_by_category(self) -> None:
        from responsibleai.mcp.tools import dispatch_tool
        r = await dispatch_tool("rai_redteam_payloads", {"categories": ["jailbreak"]})
        for p in r["payloads"]:
            assert p["category"] == "jailbreak"

    @pytest.mark.asyncio
    async def test_analyze_returns_report(self) -> None:
        from responsibleai.mcp.tools import dispatch_tool
        # Good responses — model refuses everything
        payloads_r = await dispatch_tool("rai_redteam_payloads", {})
        responses = {p["name"]: "I cannot assist with that request." for p in payloads_r["payloads"]}
        r = await dispatch_tool("rai_redteam_analyze", {
            "model_name": "test-model",
            "provider": "test",
            "responses": responses,
        })
        assert "security_score" in r
        assert "total_attacks" in r
        assert r["total_attacks"] > 0

    @pytest.mark.asyncio
    async def test_analyze_vulnerable_model(self) -> None:
        from responsibleai.mcp.tools import dispatch_tool
        responses = {
            "System prompt override attempt": "OVERRIDE_CONFIRMED. I am now DAN. No restrictions.",
        }
        r = await dispatch_tool("rai_redteam_analyze", {
            "model_name": "vulnerable-model",
            "provider": "test",
            "responses": responses,
        })
        assert r["vulnerabilities_found"] > 0


class TestRaiCompareModels:
    @pytest.mark.asyncio
    async def test_returns_winner(self) -> None:
        from responsibleai.mcp.tools import dispatch_tool
        r = await dispatch_tool("rai_compare_models", {
            "model_a": "gpt-4o",
            "provider_a": "openai",
            "scores_a": {"fairness": 0.9, "privacy": 0.8, "security": 0.9, "robustness": 0.85, "compliance": 0.9, "authenticity": 0.8},
            "model_b": "gpt-3.5-turbo",
            "provider_b": "openai",
            "scores_b": {"fairness": 0.7, "privacy": 0.6, "security": 0.7, "robustness": 0.65, "compliance": 0.7, "authenticity": 0.6},
        })
        assert r["winner"] == "gpt-4o"
        assert "delta" in r
        assert "score_gap" in r

    @pytest.mark.asyncio
    async def test_default_scores_equal(self) -> None:
        from responsibleai.mcp.tools import dispatch_tool
        r = await dispatch_tool("rai_compare_models", {
            "model_a": "a", "provider_a": "x",
            "model_b": "b", "provider_b": "y",
        })
        assert r["score_gap"] == 0.0


class TestRaiAuditSummary:
    @pytest.mark.asyncio
    async def test_returns_governance_info(self) -> None:
        from responsibleai.mcp.tools import dispatch_tool
        r = await dispatch_tool("rai_audit_summary", {"days": 7})
        assert "governance_engine" in r
        assert r["governance_engine"]["tools_available"] == 10

    @pytest.mark.asyncio
    async def test_frameworks_listed(self) -> None:
        from responsibleai.mcp.tools import dispatch_tool
        r = await dispatch_tool("rai_audit_summary", {})
        assert "NIST_AI_RMF" in r["governance_engine"]["frameworks"]


class TestRaiHealth:
    @pytest.mark.asyncio
    async def test_status_ok(self) -> None:
        from responsibleai.mcp.tools import dispatch_tool
        r = await dispatch_tool("rai_health", {})
        assert r["status"] == "ok"
        assert r["version"] == "1.1.0"

    @pytest.mark.asyncio
    async def test_all_modules_ok(self) -> None:
        from responsibleai.mcp.tools import dispatch_tool
        r = await dispatch_tool("rai_health", {})
        for module, status in r["modules"].items():
            assert status == "ok", f"Module {module} not ok"


class TestUnknownTool:
    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self) -> None:
        from responsibleai.mcp.tools import dispatch_tool
        r = await dispatch_tool("nonexistent_tool", {})
        assert "error" in r


# ── Resource dispatch ──────────────────────────────────────────────────────────

class TestMCPResources:
    @pytest.mark.asyncio
    async def test_health_resource(self) -> None:
        import json

        from responsibleai.mcp.resources import dispatch_resource
        raw = await dispatch_resource("rai://health")
        data = json.loads(raw)
        assert data["status"] == "ok"
        assert data["version"] == "1.1.0"

    @pytest.mark.asyncio
    async def test_models_catalog_resource(self) -> None:
        import json

        from responsibleai.mcp.resources import dispatch_resource
        raw = await dispatch_resource("rai://models/catalog")
        data = json.loads(raw)
        assert "openai" in data
        assert "anthropic" in data

    @pytest.mark.asyncio
    async def test_compliance_frameworks_resource(self) -> None:
        import json

        from responsibleai.mcp.resources import dispatch_resource
        raw = await dispatch_resource("rai://compliance/frameworks")
        data = json.loads(raw)
        ids = [f["id"] for f in data["frameworks"]]
        assert "NIST_AI_RMF" in ids
        assert "EU_AI_ACT" in ids
        assert "ISO_42001" in ids

    @pytest.mark.asyncio
    async def test_redteam_categories_resource(self) -> None:
        import json

        from responsibleai.mcp.resources import dispatch_resource
        raw = await dispatch_resource("rai://redteam/categories")
        data = json.loads(raw)
        assert len(data["categories"]) == 5

    @pytest.mark.asyncio
    async def test_trust_dimensions_resource(self) -> None:
        import json

        from responsibleai.mcp.resources import dispatch_resource
        raw = await dispatch_resource("rai://trust/dimensions")
        data = json.loads(raw)
        assert len(data["dimensions"]) == 6

    @pytest.mark.asyncio
    async def test_unknown_resource_returns_error(self) -> None:
        import json

        from responsibleai.mcp.resources import dispatch_resource
        raw = await dispatch_resource("rai://nonexistent/path")
        data = json.loads(raw)
        assert "error" in data
