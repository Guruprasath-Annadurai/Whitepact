"""Tests for the ResponsibleAI MCP server — tools, resources, and dispatch."""

from __future__ import annotations

import json

import pytest

from responsibleai import __version__

# ── Tool listing ───────────────────────────────────────────────────────────────

class TestMCPToolDefs:
    def test_tool_count(self) -> None:
        from responsibleai.mcp.tools import TOOL_DEFS
        assert len(TOOL_DEFS) == 29

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
            "rai_bias_evaluate", "rai_drift_check", "rai_passport_generate",
            "rai_budget_check", "rai_policy_check", "rai_stream_scan",
            "rai_benchmark", "rai_benchmark_prompts", "rai_model_route",
            "rai_pii_report", "rai_incident_log", "rai_eu_ai_act_classify",
            "rai_iso42001_gap", "rai_executive_summary", "rai_org_status",
            "rai_webhook_status", "rai_check_trust",
            "rai_memory_write_check", "rai_memory_read_check",
        }
        assert expected == names


# ── Resource listing ───────────────────────────────────────────────────────────

class TestMCPResourceDefs:
    def test_canonical_resource_count(self) -> None:
        from responsibleai.mcp.resources import _CANONICAL_RESOURCE_DEFS
        assert len(_CANONICAL_RESOURCE_DEFS) == 10

    def test_advertised_resource_count_is_doubled_for_dual_scheme(self) -> None:
        # MIGRATION_WHITEPACT_V2.md Section 6: every canonical resource is
        # advertised under both whitepact:// and rai://.
        from responsibleai.mcp.resources import _CANONICAL_RESOURCE_DEFS, RESOURCE_DEFS
        assert len(RESOURCE_DEFS) == 2 * len(_CANONICAL_RESOURCE_DEFS)

    def test_all_resources_have_uri_and_name(self) -> None:
        from responsibleai.mcp.resources import RESOURCE_DEFS
        for res in RESOURCE_DEFS:
            assert res.uri
            assert res.name

    def test_all_resources_json_mime(self) -> None:
        from responsibleai.mcp.resources import RESOURCE_DEFS
        for res in RESOURCE_DEFS:
            assert res.mimeType == "application/json"

    def test_every_canonical_uri_has_a_whitepact_twin(self) -> None:
        from responsibleai.mcp.resources import RESOURCE_DEFS
        uris = {str(r.uri) for r in RESOURCE_DEFS}
        legacy_uris = {u for u in uris if u.startswith("rai://")}
        for legacy_uri in legacy_uris:
            whitepact_uri = "whitepact://" + legacy_uri.removeprefix("rai://")
            assert whitepact_uri in uris, f"missing whitepact:// twin for {legacy_uri}"

    def test_whitepact_scheme_listed_before_legacy(self) -> None:
        # Not load-bearing behavior, but documents the deliberate choice
        # (see resources.py's RESOURCE_DEFS comment) so a client that only
        # reads the first N results sees the preferred scheme.
        from responsibleai.mcp.resources import RESOURCE_DEFS
        assert str(RESOURCE_DEFS[0].uri).startswith("whitepact://")


class TestMCPResourceDualScheme:
    """dispatch_resource() must resolve whitepact:// identically to the
    legacy rai:// scheme it aliases — see MIGRATION_WHITEPACT_V2.md
    Section 6."""

    async def test_whitepact_and_legacy_health_are_identical(self) -> None:
        from responsibleai.mcp.resources import dispatch_resource
        legacy = await dispatch_resource("rai://health")
        new = await dispatch_resource("whitepact://health")
        assert legacy == new

    async def test_whitepact_and_legacy_models_catalog_are_identical(self) -> None:
        from responsibleai.mcp.resources import dispatch_resource
        legacy = await dispatch_resource("rai://models/catalog")
        new = await dispatch_resource("whitepact://models/catalog")
        assert legacy == new

    async def test_health_reports_accurate_tool_and_resource_counts(self) -> None:
        # Regression coverage: this exact field was hardcoded and stale
        # (claimed 26 tools when the real count was 27) before this
        # migration made it read from TOOL_DEFS/_CANONICAL_RESOURCE_DEFS.
        import json

        from responsibleai.mcp.resources import _CANONICAL_RESOURCE_DEFS, dispatch_resource
        from responsibleai.mcp.tools import TOOL_DEFS
        payload = json.loads(await dispatch_resource("whitepact://health"))
        assert payload["tools_available"] == len(TOOL_DEFS)
        assert payload["resources_available"] == len(_CANONICAL_RESOURCE_DEFS)

    async def test_unknown_whitepact_uri_reports_not_found_like_legacy_scheme(self) -> None:
        import json

        from responsibleai.mcp.resources import dispatch_resource
        legacy = json.loads(await dispatch_resource("rai://not-a-real-resource"))
        new = json.loads(await dispatch_resource("whitepact://not-a-real-resource"))
        assert "error" in legacy
        # The normalized (rai://) form appears in the error either way --
        # normalization happens before the not-found fallback runs, so
        # both inputs report the same underlying, resolved URI.
        assert legacy == new


class TestMCPServerIdentity:
    def test_server_name_is_whitepact(self) -> None:
        from responsibleai.mcp.server import server
        assert server.name == "whitepact"


class TestCliEntryPoints:
    """MIGRATION_WHITEPACT_V2.md Section 4: whitepact/whitepact-mcp/
    whitepact-mcp-http are additive, identical entry-point functions to
    their legacy counterparts — nothing removed, nothing repointed."""

    def test_pyproject_declares_both_legacy_and_preferred_scripts(self) -> None:
        import tomllib
        from pathlib import Path

        pyproject = tomllib.loads(
            (Path(__file__).parent.parent / "pyproject.toml").read_text()
        )
        scripts = pyproject["project"]["scripts"]
        assert scripts["responsibleai-mcp"] == scripts["whitepact-mcp"]
        assert scripts["responsibleai-mcp-http"] == scripts["whitepact-mcp-http"]
        assert scripts["responsibleai"] == scripts["whitepact"]

    def test_no_legacy_script_was_removed(self) -> None:
        import tomllib
        from pathlib import Path

        pyproject = tomllib.loads(
            (Path(__file__).parent.parent / "pyproject.toml").read_text()
        )
        scripts = set(pyproject["project"]["scripts"])
        legacy = {"biasbuster", "responsibleai", "responsibleai-mcp", "responsibleai-mcp-http"}
        assert legacy <= scripts


class TestInvocationNameObservability:
    """Section 4: whichever script name actually launched the process is
    logged (stderr/structured logging), never assumed or hardcoded."""

    def test_invoked_as_reads_argv0_basename(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from responsibleai.mcp.server import _invoked_as
        monkeypatch.setattr("sys.argv", ["/usr/local/bin/whitepact-mcp"])
        assert _invoked_as() == "whitepact-mcp"

    def test_invoked_as_handles_empty_argv(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from responsibleai.mcp.server import _invoked_as
        monkeypatch.setattr("sys.argv", [])
        assert _invoked_as() == "unknown"

    def test_legacy_invocation_logs_the_preferred_alternative(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
    ) -> None:
        from responsibleai.mcp.server import _log_invocation_name
        monkeypatch.setattr("sys.argv", ["/usr/local/bin/responsibleai-mcp"])
        with caplog.at_level("INFO", logger="responsibleai.mcp"):
            _log_invocation_name("stdio server")
        assert "whitepact-mcp" in caplog.text
        assert "responsibleai-mcp" in caplog.text

    def test_legacy_http_invocation_names_the_http_preferred_alternative(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
    ) -> None:
        from responsibleai.mcp.server import _log_invocation_name
        monkeypatch.setattr("sys.argv", ["/usr/local/bin/responsibleai-mcp-http"])
        with caplog.at_level("INFO", logger="responsibleai.mcp"):
            _log_invocation_name("http+sse server")
        # Regression guard: an earlier draft of this string-built the
        # suffix wrong and could produce "whitepact-mcp'-http" instead of
        # "whitepact-mcp-http" — assert the correctly-joined form appears.
        assert "whitepact-mcp-http" in caplog.text

    def test_preferred_invocation_does_not_mention_legacy(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
    ) -> None:
        from responsibleai.mcp.server import _log_invocation_name
        monkeypatch.setattr("sys.argv", ["/usr/local/bin/whitepact-mcp"])
        with caplog.at_level("INFO", logger="responsibleai.mcp"):
            _log_invocation_name("stdio server")
        assert "legacy" not in caplog.text.lower()


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
        assert r["governance_engine"]["tools_available"] == 29

    @pytest.mark.asyncio
    async def test_frameworks_listed(self) -> None:
        from responsibleai.mcp.tools import dispatch_tool
        r = await dispatch_tool("rai_audit_summary", {})
        assert "NIST_AI_RMF" in r["governance_engine"]["frameworks"]


class TestStructuredToolOutput:
    """Structured tool-output contracts (spec 2025-06-18): `_call_tool`
    returns `(content, structuredContent)` tuples, which the SDK's
    `@server.call_tool()` decorator turns into a `CallToolResult` with
    both populated -- verified end-to-end (over the wire) in
    test_mcp_http_transport.py; these test the raw function's contract
    directly, the same way test_mcp_server_gating.py does."""

    async def test_text_and_structured_helper_shapes(self) -> None:
        from responsibleai.mcp.server import _text_and_structured

        content, structured = _text_and_structured({"status": "ok", "n": 1})
        assert structured == {"status": "ok", "n": 1}
        assert len(content) == 1
        assert content[0].type == "text"
        assert json.loads(content[0].text) == structured

    async def test_call_tool_returns_tuple_with_matching_content(self) -> None:
        from responsibleai.mcp import server as mcp_server

        content, structured = await mcp_server._call_tool("rai_health", {})
        assert isinstance(structured, dict)
        assert structured["status"] == "ok"
        assert json.loads(content[0].text) == structured


class TestRaiHealth:
    @pytest.mark.asyncio
    async def test_status_ok(self) -> None:
        from responsibleai.mcp.tools import dispatch_tool
        r = await dispatch_tool("rai_health", {})
        assert r["status"] == "ok"
        assert r["version"] == __version__

    @pytest.mark.asyncio
    async def test_all_modules_ok(self) -> None:
        from responsibleai.mcp.tools import dispatch_tool
        r = await dispatch_tool("rai_health", {})
        for module, status in r["modules"].items():
            assert status == "ok", f"Module {module} not ok"


class TestRaiIncidentLog:
    @pytest.mark.asyncio
    async def test_builds_structured_record(self) -> None:
        from responsibleai.mcp.tools import dispatch_tool
        r = await dispatch_tool("rai_incident_log", {
            "incident_type": "pii_leak", "severity": "critical",
            "description": "SSN found in completion.",
        })
        assert r["incident_type"] == "pii_leak"
        assert r["severity"] == "critical"
        assert r["sla_resolution_hours"] == 1
        assert r["status"] == "OPEN"
        assert r["siem_event_type"] == "DATA_EXPOSURE"

    @pytest.mark.asyncio
    async def test_persist_instructions_point_at_real_endpoint(self) -> None:
        """Regression check for the gap the 2026-07-21 tabletop drill found:
        this field used to claim a POST /api/v1/incidents endpoint existed
        when it didn't. It's real now (POST /api/incidents) — assert the
        tool says so instead of pointing at a 404."""
        from responsibleai.mcp.tools import dispatch_tool
        r = await dispatch_tool("rai_incident_log", {"description": "test"})
        assert "POST /api/incidents" in r["persist_instructions"]
        assert "/api/v1/incidents" not in r["persist_instructions"]


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
        assert data["version"] == __version__

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
