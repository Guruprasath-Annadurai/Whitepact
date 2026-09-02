"""OpenAI Plugins Directory submission — release-critical regression
suite. Asserts every automatable case from review_contract.py against
the real MCP tool handlers via _dispatch_tool_unchecked(), exactly as they would
be invoked over the MCP transport.

Scope, stated honestly: this suite verifies *server-side* correctness
-- does WhitePact's own code produce the documented result for the
exact submitted inputs. It cannot verify ChatGPT's tool-selection
reasoning, web/mobile client parity, or what OpenAI's own reviewer
actually observed -- those remain NOT VERIFIED and require manual
client-side testing (see compliance/OPENAI_PLUGIN_SUBMISSION_PREP.md).
"""

from __future__ import annotations

import json
import re

import pytest

from responsibleai.mcp.tools import TOOL_DEFS, _dispatch_tool_unchecked
from tests.openai_review.review_contract import REVIEW_CONTRACT as CONTRACT


class TestReviewContractGoldenFileIsValid:
    """The golden file itself must stay structurally sound -- a broken
    JSON file here would silently disable every test below it."""

    def test_file_parses(self) -> None:
        assert CONTRACT["positive"]
        assert CONTRACT["negative"]

    def test_every_positive_case_has_required_fields(self) -> None:
        for case in CONTRACT["positive"]:
            assert case["review_test_id"]
            assert case["expected_tool"]
            assert case["expected_result_contract"]

    def test_every_case_id_is_unique(self) -> None:
        ids = [c["review_test_id"] for c in CONTRACT["positive"] + CONTRACT["negative"]]
        assert len(ids) == len(set(ids))

    def test_every_expected_tool_actually_exists(self) -> None:
        """A case referencing a tool name that doesn't exist in TOOL_DEFS
        is worse than a failing test -- it's a silently-dead test."""
        real_names = {t.name for t in TOOL_DEFS}
        for case in CONTRACT["positive"]:
            assert case["expected_tool"] in real_names, (
                f"{case['review_test_id']} references unknown tool {case['expected_tool']!r}"
            )


class TestPositiveCaseTCP1PiiScan:
    async def test_matches_documented_contract(self) -> None:
        case = next(c for c in CONTRACT["positive"] if c["review_test_id"] == "TC-P1")
        result = await _dispatch_tool_unchecked(case["expected_tool"], case["expected_arguments"])
        assert "error" not in result
        for key in case["expected_result_contract"]["required_keys"]:
            assert key in result, f"{case['review_test_id']}: missing key {key!r}"
        assert result["has_pii"] == case["expected_result_contract"]["has_pii"]
        assert "john@example.com" not in result["redacted_text"]

    async def test_repeatable_20_runs_structurally_identical(self) -> None:
        """Determinism check (Phase 6): identical input, run repeatedly,
        must never change which keys are present or their types."""
        args = {"text": "Contact John at john@example.com or 555-123-4567."}
        first = await _dispatch_tool_unchecked("rai_scan", args)
        for _ in range(19):
            r = await _dispatch_tool_unchecked("rai_scan", args)
            assert set(r.keys()) == set(first.keys())
            assert r["is_blocked"] == first["is_blocked"]
            assert r["has_pii"] == first["has_pii"]
            assert r["redacted_text"] == first["redacted_text"]


class TestPositiveCaseTCP2TrustScore:
    async def test_matches_documented_contract(self) -> None:
        case = next(c for c in CONTRACT["positive"] if c["review_test_id"] == "TC-P2")
        result = await _dispatch_tool_unchecked(case["expected_tool"], case["expected_arguments"])
        assert "error" not in result
        contract = case["expected_result_contract"]
        for key in contract["required_keys"]:
            assert key in result, f"{case['review_test_id']}: missing key {key!r}"
        lo, hi = contract["score_range"]
        assert lo <= result["score"] <= hi
        assert lo <= result["trust_score"] <= hi
        assert result["score"] == result["trust_score"]
        assert re.match(contract["grade_pattern"], result["grade"])
        assert result["risk_tier"] in contract["risk_tier_enum"]
        assert result["risk_tier"] == result["risk"]

    async def test_repeatable_20_runs_structurally_identical(self) -> None:
        args = {
            "fairness": 0.8,
            "privacy": 0.9,
            "security": 0.7,
            "robustness": 0.85,
            "compliance": 0.9,
            "authenticity": 0.95,
        }
        first = await _dispatch_tool_unchecked("rai_trust_score", args)
        for _ in range(19):
            r = await _dispatch_tool_unchecked("rai_trust_score", args)
            assert set(r.keys()) == set(first.keys())
            assert r["score"] == first["score"]
            assert r["grade"] == first["grade"]
            assert r["risk_tier"] == first["risk_tier"]
            # `timestamp` is expected to vary -- cosmetic nondeterminism,
            # not asserted equal, but must always be present and a string.
            assert isinstance(r["timestamp"], str)


class TestPositiveCaseTCP3EuAiAct:
    async def test_matches_documented_contract(self) -> None:
        case = next(c for c in CONTRACT["positive"] if c["review_test_id"] == "TC-P3")
        result = await _dispatch_tool_unchecked(case["expected_tool"], case["expected_arguments"])
        assert "error" not in result
        contract = case["expected_result_contract"]
        for key in contract["required_keys"]:
            assert key in result
        assert result["risk_tier"] in contract["risk_tier_enum"]
        assert result["risk_tier"] == contract["expected_risk_tier_for_this_case"]

    async def test_deployment_sector_is_required_forcing_unambiguous_routing(self) -> None:
        """Schema-level routing-safety check (Phase 3/8): deployment_sector
        must be a required enum, not a free-form optional string -- an
        optional/free-form field would let ChatGPT omit or mistype the
        sector, producing an unpredictable classification."""
        tool = next(t for t in TOOL_DEFS if t.name == "rai_eu_ai_act_classify")
        assert "deployment_sector" in tool.inputSchema["required"]
        assert "enum" in tool.inputSchema["properties"]["deployment_sector"]
        assert "employment" in tool.inputSchema["properties"]["deployment_sector"]["enum"]


class TestPositiveCaseTCP4Hallucination:
    async def test_matches_documented_contract(self) -> None:
        case = next(c for c in CONTRACT["positive"] if c["review_test_id"] == "TC-P4")
        result = await _dispatch_tool_unchecked(case["expected_tool"], case["expected_arguments"])
        assert "error" not in result
        contract = case["expected_result_contract"]
        for key in contract["required_keys"]:
            assert key in result
        assert result["hallucination_detected"] is contract["hallucination_detected"]
        assert result["source_contradiction_detected"] is True

    async def test_pre_fix_regression_this_exact_input_no_longer_fails(self) -> None:
        """Direct regression test for the empirically-confirmed failure:
        this exact submitted prompt, split the way a well-behaved model
        would split it, previously produced risk_level='low' -- the
        opposite of the documented contract."""
        result = await _dispatch_tool_unchecked(
            "rai_hallucination",
            {"text": "the meeting is Wednesday", "source": "the meeting is Tuesday"},
        )
        assert result["hallucination_detected"] is True
        assert result["risk_level"] in ("high", "critical")

    async def test_no_source_supplied_does_not_false_positive(self) -> None:
        """The contradiction check must never fire when no source was
        given -- false positives would be worse than the original gap."""
        result = await _dispatch_tool_unchecked("rai_hallucination", {"text": "The sky is blue."})
        assert result["source_contradiction_detected"] is False

    async def test_agreeing_source_does_not_false_positive(self) -> None:
        result = await _dispatch_tool_unchecked(
            "rai_hallucination",
            {"text": "the meeting is Tuesday", "source": "the meeting is Tuesday"},
        )
        assert result["source_contradiction_detected"] is False

    async def test_repeatable_20_runs_structurally_identical(self) -> None:
        args = {"text": "the meeting is Wednesday", "source": "the meeting is Tuesday"}
        first = await _dispatch_tool_unchecked("rai_hallucination", args)
        for _ in range(19):
            r = await _dispatch_tool_unchecked("rai_hallucination", args)
            assert r == first  # fully deterministic, no timestamp/uuid in this payload


class TestPositiveCaseTCP5OrgStatus:
    async def test_no_context_calling_convention_still_uses_supplied_data_only(self) -> None:
        """The schema still has no org_id/api_key parameter -- real org
        data comes from the hosted transport's authenticated request
        context (mcp/server.py's `_current_org`), not a caller-supplied
        argument; see tests/test_mcp_org_status_live.py for the
        authenticated path. A direct _dispatch_tool_unchecked() call outside any
        request context (what this test exercises) has no such context,
        so it still returns the caller-supplied-only rollup -- this
        test exists so that fallback behavior cannot silently regress."""
        tool = next(t for t in TOOL_DEFS if t.name == "rai_org_status")
        assert "org_id" not in tool.inputSchema["properties"]
        assert "api_key" not in tool.inputSchema["properties"]
        result = await _dispatch_tool_unchecked("rai_org_status", {})
        assert "org_id" not in result  # no request context -> no real org data
        assert result["models"]["total"] == 0
        assert result["health_status"] == "HEALTHY"  # correct default, not fabricated

    async def test_corrected_contract_with_supplied_data(self) -> None:
        case = next(c for c in CONTRACT["positive"] if c["review_test_id"] == "TC-P5")
        contract = case["expected_result_contract"]
        result = await _dispatch_tool_unchecked("rai_org_status", contract["corrected_arguments"])
        assert "error" not in result
        for key in contract["required_keys"]:
            assert key in result
        assert result["models"]["grade_distribution"]["A"] == 1
        assert result["operations"]["open_incidents"] == 2


class TestNegativeCaseTCN1NoDeleteTool:
    def test_no_tool_is_marked_destructive(self) -> None:
        for tool in TOOL_DEFS:
            assert tool.annotations is not None
            assert tool.annotations.destructiveHint is False, (
                f"{tool.name} is marked destructive -- TC-N1 assumes none are"
            )

    def test_no_tool_name_implies_deletion(self) -> None:
        for tool in TOOL_DEFS:
            assert "delete" not in tool.name.lower()
            assert "remove" not in tool.name.lower()


class TestNegativeCaseTCN2NoContentGenerationTool:
    def test_no_tool_named_or_described_as_content_generator(self) -> None:
        banned_terms = ("marketing copy", "generate content", "write copy")
        for tool in TOOL_DEFS:
            assert tool.description is not None
            desc_lower = tool.description.lower()
            for term in banned_terms:
                assert term not in desc_lower, f"{tool.name} description mentions {term!r}"


class TestNegativeCaseTCN3TrustScoreDefaultsAreSilent:
    async def test_all_six_dimensions_default_to_neutral_0_5(self) -> None:
        """Confirms the schema-level fact the negative case relies on:
        rai_trust_score never raises/clarifies on missing input, it
        silently defaults every dimension to 0.5. Whether ChatGPT asks
        for clarification instead of calling with these defaults is a
        client-reasoning behavior this test cannot verify."""
        tool = next(t for t in TOOL_DEFS if t.name == "rai_trust_score")
        assert tool.inputSchema.get("required") in (None, [])
        for dim in ("fairness", "privacy", "security", "robustness", "compliance", "authenticity"):
            assert tool.inputSchema["properties"][dim]["default"] == 0.5

        result = await _dispatch_tool_unchecked("rai_trust_score", {})
        assert result["score"] == 50.0
        assert result["grade"] in ("D", "F", "C")


class TestErrorHandlingHardening:
    """Phase 5 of the review methodology: no MCP tool should ever expose
    a raw stack trace, and unknown tools/malformed input must fail
    predictably, not crash the dispatch loop."""

    async def test_unknown_tool_returns_structured_error_not_exception(self) -> None:
        result = await _dispatch_tool_unchecked("rai_does_not_exist", {})
        assert result == {"error": "Unknown tool: rai_does_not_exist"}

    async def test_missing_required_field_does_not_leak_traceback(self) -> None:
        result = await _dispatch_tool_unchecked("rai_eu_ai_act_classify", {})
        # Missing required "deployment_sector"/"system_description" --
        # MCP schema validation happens client-side per the spec, but the
        # server-side handler itself must not crash on missing keys.
        assert "Traceback" not in json.dumps(result)
        assert 'File "' not in json.dumps(result)

    async def test_wrong_type_input_does_not_crash_dispatch(self) -> None:
        result = await _dispatch_tool_unchecked("rai_trust_score", {"fairness": "not-a-number"})
        assert "error" in result
        assert "Traceback" not in json.dumps(result)


@pytest.mark.parametrize("tool_name", [c["expected_tool"] for c in CONTRACT["positive"]])
def test_every_reviewed_tool_is_readonly_nondestructive(tool_name: str) -> None:
    """All 27 (now 30) tools are marketed as read-only/non-destructive
    in the submission listing itself -- verify the annotation actually
    says so for every tool the review contract touches."""
    tool = next(t for t in TOOL_DEFS if t.name == tool_name)
    assert tool.annotations is not None
    assert tool.annotations.readOnlyHint is True
    assert tool.annotations.destructiveHint is False
