"""
LLM integration tests — full governance pipeline with mocked provider APIs.

Uses respx to intercept HTTP calls to OpenAI and Anthropic, then runs the
response text through the full evaluation stack: GuardrailsEngine →
HallucinationDetector → TrustScoreEngine → CostTracker.

No real API keys or network access required.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from biasbuster.providers.anthropic_provider import AnthropicProvider
from biasbuster.providers.base import CompletionRequest
from biasbuster.providers.openai_provider import OpenAIProvider
from responsibleai.cost.models import BudgetPolicy, TokenUsage
from responsibleai.cost.tracker import CostTracker
from responsibleai.guardrails.engine import GuardrailsEngine
from responsibleai.hallucination.detector import HallucinationDetector
from responsibleai.trust.score import TrustScoreEngine

# ── Helpers ───────────────────────────────────────────────────────────────────

def _openai_response(text: str, model: str = "gpt-4o",
                     in_tokens: int = 50, out_tokens: int = 100) -> MagicMock:
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = text
    resp.model = model
    resp.usage.prompt_tokens = in_tokens
    resp.usage.completion_tokens = out_tokens
    return resp


def _anthropic_response(text: str, model: str = "claude-3-5-sonnet-20241022",
                        in_tokens: int = 50, out_tokens: int = 100) -> MagicMock:
    resp = MagicMock()
    resp.content = [MagicMock(text=text)]
    resp.model = model
    resp.usage.input_tokens = in_tokens
    resp.usage.output_tokens = out_tokens
    return resp


# ── Provider integration ───────────────────────────────────────────────────────

class TestOpenAIPipelineIntegration:
    @pytest.mark.asyncio
    async def test_clean_response_passes_guardrails(self):
        provider = OpenAIProvider(api_key="sk-test")
        safe_text = "The quarterly earnings exceeded analyst expectations by 12%."
        mock_resp = _openai_response(safe_text)

        with patch.object(provider._client.chat.completions, "create", AsyncMock(return_value=mock_resp)):
            result = await provider.complete(CompletionRequest(prompt="Summarize Q4 results."))

        guardrails = GuardrailsEngine()
        scan = guardrails.scan(result.text)
        assert not scan.is_blocked
        assert len(scan.pii_findings) == 0

    @pytest.mark.asyncio
    async def test_pii_response_blocked_by_guardrails(self):
        provider = OpenAIProvider(api_key="sk-test")
        pii_text = "The customer SSN is 123-45-6789 and email is john@example.com."
        mock_resp = _openai_response(pii_text)

        with patch.object(provider._client.chat.completions, "create", AsyncMock(return_value=mock_resp)):
            result = await provider.complete(CompletionRequest(prompt="Get customer info."))

        guardrails = GuardrailsEngine()
        scan = guardrails.scan(result.text)
        assert scan.is_blocked
        assert len(scan.pii_findings) > 0

    @pytest.mark.asyncio
    async def test_response_scored_by_hallucination_detector(self):
        provider = OpenAIProvider(api_key="sk-test")
        hedging_text = (
            "It might be the case that AI could possibly replace some jobs, "
            "but it may also create new ones."
        )
        mock_resp = _openai_response(hedging_text)

        with patch.object(provider._client.chat.completions, "create", AsyncMock(return_value=mock_resp)):
            result = await provider.complete(CompletionRequest(prompt="Will AI replace jobs?"))

        detector = HallucinationDetector()
        analysis = detector.analyze(result.text)
        assert 0.0 <= analysis.hallucination_risk <= 1.0
        assert analysis.risk_level in ("low", "medium", "high", "critical")

    @pytest.mark.asyncio
    async def test_token_usage_tracked(self):
        provider = OpenAIProvider(api_key="sk-test")
        mock_resp = _openai_response("The answer is 42.", in_tokens=25, out_tokens=10)

        with patch.object(provider._client.chat.completions, "create", AsyncMock(return_value=mock_resp)):
            result = await provider.complete(CompletionRequest(prompt="What is the answer?"))

        assert result.input_tokens == 25
        assert result.output_tokens == 10

        tracker = CostTracker()
        usage = TokenUsage.create(
            provider="openai", model="gpt-4o",
            input_tokens=result.input_tokens, output_tokens=result.output_tokens,
        )
        record = tracker.record(usage)
        assert record.total_cost > 0

    @pytest.mark.asyncio
    async def test_full_evaluation_pipeline(self):
        """End-to-end: call LLM → scan → evaluate trust score."""
        provider = OpenAIProvider(api_key="sk-test")
        safe_response = "Our model demonstrates strong alignment with fairness principles across all demographic groups."
        mock_resp = _openai_response(safe_response, in_tokens=120, out_tokens=80)

        with patch.object(provider._client.chat.completions, "create", AsyncMock(return_value=mock_resp)):
            completion = await provider.complete(CompletionRequest(prompt="Describe model fairness."))

        guardrails = GuardrailsEngine()
        scan = guardrails.scan(completion.text)
        assert not scan.is_blocked

        hallucination = HallucinationDetector()
        h_result = hallucination.analyze(completion.text)

        trust_engine = TrustScoreEngine()
        fairness_score = 1.0 - h_result.hallucination_risk
        score = trust_engine.compute(
            fairness=fairness_score,
            privacy=1.0 if not scan.is_blocked else 0.5,
            security=0.85,
            robustness=0.80,
            compliance=0.90,
            authenticity=1.0 - h_result.hallucination_risk,
        )
        assert score.overall > 0
        assert score.grade in ("A", "B", "C", "D", "F")

        tracker = CostTracker()
        usage = TokenUsage.create(
            provider="openai", model="gpt-4o",
            input_tokens=completion.input_tokens or 0,
            output_tokens=completion.output_tokens or 0,
        )
        record = tracker.record(usage)
        assert record.total_cost >= 0

    @pytest.mark.asyncio
    async def test_multiple_models_cost_comparison(self):
        """Verify cost tracking works across model tiers."""
        tracker = CostTracker()

        models = [
            ("openai", "gpt-4o",        1000, 500),
            ("openai", "gpt-4o-mini",   1000, 500),
            ("anthropic", "claude-3-5-sonnet-20241022", 1000, 500),
            ("anthropic", "claude-3-haiku-20240307",    1000, 500),
        ]
        costs = {}
        for provider, model, inp, out in models:
            u = TokenUsage.create(provider=provider, model=model,
                                  input_tokens=inp, output_tokens=out)
            r = tracker.record(u)
            costs[f"{provider}/{model}"] = r.total_cost

        assert costs["openai/gpt-4o"] > costs["openai/gpt-4o-mini"]
        assert all(c > 0 for c in costs.values())


class TestAnthropicPipelineIntegration:
    @pytest.mark.asyncio
    async def test_clean_response_passes_guardrails(self):
        provider = AnthropicProvider(api_key="sk-ant-test")
        safe_text = "Machine learning models are trained on large datasets to recognize patterns."
        mock_resp = _anthropic_response(safe_text)

        with patch.object(provider._client.messages, "create", AsyncMock(return_value=mock_resp)):
            result = await provider.complete(CompletionRequest(prompt="Explain ML."))

        guardrails = GuardrailsEngine()
        scan = guardrails.scan(result.text)
        assert not scan.is_blocked

    @pytest.mark.asyncio
    async def test_pii_in_response_detected(self):
        provider = AnthropicProvider(api_key="sk-ant-test")
        pii_text = "Please contact the team at alice@company.org or reference SSN 987-65-4321."
        mock_resp = _anthropic_response(pii_text)

        with patch.object(provider._client.messages, "create", AsyncMock(return_value=mock_resp)):
            result = await provider.complete(CompletionRequest(prompt="Get contact info."))

        guardrails = GuardrailsEngine()
        scan = guardrails.scan(result.text)
        assert len(scan.pii_findings) > 0

    @pytest.mark.asyncio
    async def test_token_usage_feeds_cost_tracker(self):
        provider = AnthropicProvider(api_key="sk-ant-test")
        mock_resp = _anthropic_response("Differential privacy adds calibrated noise.", in_tokens=30, out_tokens=15)

        with patch.object(provider._client.messages, "create", AsyncMock(return_value=mock_resp)):
            result = await provider.complete(CompletionRequest(prompt="Explain DP."))

        tracker = CostTracker()
        usage = TokenUsage.create(
            provider="anthropic", model="claude-3-5-sonnet-20241022",
            input_tokens=result.input_tokens, output_tokens=result.output_tokens,
        )
        record = tracker.record(usage)
        assert record.total_cost > 0
        assert record.usage.provider == "anthropic"

    @pytest.mark.asyncio
    async def test_consistency_check_with_candidates(self):
        provider = AnthropicProvider(api_key="sk-ant-test")
        claim = "The Earth orbits the Sun in approximately 365.25 days."
        candidates = [
            "The Earth takes about one year to orbit the Sun.",
            "The orbital period of Earth is roughly 365 days.",
        ]
        mock_resp = _anthropic_response(claim)

        with patch.object(provider._client.messages, "create", AsyncMock(return_value=mock_resp)):
            result = await provider.complete(CompletionRequest(prompt="How long does Earth take to orbit?"))

        detector = HallucinationDetector()
        analysis = detector.analyze(result.text, candidates=candidates)
        assert analysis.consistency_score >= 0
        assert analysis.hallucination_risk < 0.9


# ── Cross-provider comparison ─────────────────────────────────────────────────

class TestCrossProviderComparison:
    @pytest.mark.asyncio
    async def test_same_prompt_different_providers(self):
        """Both providers should produce scannable, evaluatable responses."""
        responses = {
            "openai": "Responsible AI requires fairness, transparency, and accountability in model design.",
            "anthropic": "The key principles include fairness, privacy protection, transparency, and human oversight.",
        }

        guardrails = GuardrailsEngine()
        detector = HallucinationDetector()
        trust_engine = TrustScoreEngine()

        for provider, text in responses.items():
            scan = guardrails.scan(text)
            detector.analyze(text)
            score = trust_engine.compute(
                fairness=0.85, privacy=0.90, security=0.85,
                robustness=0.80, compliance=0.90, authenticity=0.85,
            )
            assert not scan.is_blocked, f"{provider} response unexpectedly blocked"
            assert score.grade in ("A", "B", "C", "D", "F")

    def test_guardrails_catches_pii_regardless_of_provider(self):
        pii_texts = [
            "Customer SSN: 123-45-6789",
            "Billing email: billing@acme-corp.com and card 4111111111111111",
        ]
        guardrails = GuardrailsEngine()
        for text in pii_texts:
            scan = guardrails.scan(text)
            assert scan.is_blocked, f"Expected PII text to be blocked: {text[:40]}"
            assert len(scan.pii_findings) > 0

    def test_hallucination_detector_flags_uncertainty(self):
        uncertain_text = (
            "It is possible that maybe AI might potentially replace some jobs, "
            "but it could also perhaps create new opportunities."
        )
        detector = HallucinationDetector()
        result = detector.analyze(uncertain_text)
        assert result.hedging_score > 0

    def test_trust_score_reflects_scan_result(self):
        trust_engine = TrustScoreEngine()
        guardrails = GuardrailsEngine()

        clean_text = "Our AI model is trained with privacy-preserving techniques."
        pii_text   = "User SSN: 123-45-6789, Credit card: 4111111111111111"

        clean_scan = guardrails.scan(clean_text)
        pii_scan   = guardrails.scan(pii_text)

        privacy_clean = 0.95 if not clean_scan.is_blocked else 0.30
        privacy_pii   = 0.95 if not pii_scan.is_blocked   else 0.30

        score_clean = trust_engine.compute(fairness=0.80, privacy=privacy_clean,
                                           security=0.80, robustness=0.80,
                                           compliance=0.80, authenticity=0.80)
        score_pii   = trust_engine.compute(fairness=0.80, privacy=privacy_pii,
                                           security=0.80, robustness=0.80,
                                           compliance=0.80, authenticity=0.80)
        assert score_clean.overall > score_pii.overall


# ── Budget enforcement with realistic LLM usage ───────────────────────────────

class TestBudgetEnforcement:
    def test_budget_alert_triggered(self):
        policy = BudgetPolicy(monthly_limit_usd=0.01)  # very tight budget
        tracker = CostTracker(policy=policy)

        for _ in range(20):
            u = TokenUsage.create(provider="openai", model="gpt-4o",
                                  input_tokens=5000, output_tokens=2000)
            tracker.record(u)

        status = tracker.check_budget()
        assert status.is_exceeded

    def test_cost_scales_with_model_tier(self):
        tracker = CostTracker()

        cheap = TokenUsage.create(provider="openai", model="gpt-4o-mini",
                                  input_tokens=10_000, output_tokens=5_000)
        premium = TokenUsage.create(provider="openai", model="gpt-4o",
                                    input_tokens=10_000, output_tokens=5_000)
        r_cheap   = tracker.record(cheap)
        r_premium = tracker.record(premium)

        assert r_premium.total_cost > r_cheap.total_cost

    def test_team_attribution(self):
        tracker = CostTracker()
        teams = ["engineering", "product", "marketing"]
        for team in teams:
            u = TokenUsage.create(provider="openai", model="gpt-4o",
                                  input_tokens=1000, output_tokens=500, team=team)
            tracker.record(u)

        breakdown = tracker.get_team_breakdown()
        for team in teams:
            assert team in breakdown
