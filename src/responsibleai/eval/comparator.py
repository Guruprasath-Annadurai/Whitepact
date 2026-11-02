"""A/B model comparator — evaluates two response sets on identical prompts."""

from __future__ import annotations

from responsibleai.eval.models import (
    ComparisonResult,
    EvalPrompt,
    ModelResponse,
    PromptComparisonResult,
)
from responsibleai.guardrails.engine import GuardrailsEngine
from responsibleai.hallucination.detector import HallucinationDetector
from responsibleai.trust.score import TrustScoreEngine


class ModelComparator:
    """Compare two models side-by-side on the same prompt set.

    Each response is scored using the TrustScoreEngine (composite 0-100).
    PII and hallucination findings apply negative adjustments before ranking.
    """

    def __init__(
        self,
        trust_engine: TrustScoreEngine | None = None,
        guardrails: GuardrailsEngine | None = None,
        hallucination: HallucinationDetector | None = None,
    ) -> None:
        self._trust = trust_engine or TrustScoreEngine()
        self._guardrails = guardrails or GuardrailsEngine()
        self._hallucination = hallucination or HallucinationDetector()

    def compare(
        self,
        prompts: list[EvalPrompt],
        responses_a: list[ModelResponse],
        responses_b: list[ModelResponse],
        model_a: str,
        model_b: str,
        provider_a: str = "unknown",
        provider_b: str = "unknown",
    ) -> ComparisonResult:
        result = ComparisonResult(
            model_a=model_a,
            model_b=model_b,
            provider_a=provider_a,
            provider_b=provider_b,
        )
        ra_map = {r.prompt_id: r for r in responses_a}
        rb_map = {r.prompt_id: r for r in responses_b}

        for prompt in prompts:
            ra = ra_map.get(prompt.id)
            rb = rb_map.get(prompt.id)
            if ra is None or rb is None:
                continue

            score_a, hall_a, pii_a = self._evaluate(ra.response)
            score_b, hall_b, pii_b = self._evaluate(rb.response)

            adj_a = max(0.0, score_a - (20.0 if pii_a else 0.0) - hall_a * 15.0)
            adj_b = max(0.0, score_b - (20.0 if pii_b else 0.0) - hall_b * 15.0)

            if adj_a > adj_b + 1.0:
                winner = "model_a"
            elif adj_b > adj_a + 1.0:
                winner = "model_b"
            else:
                winner = "tie"

            result.prompt_results.append(
                PromptComparisonResult(
                    prompt_id=prompt.id,
                    prompt=prompt.prompt,
                    response_a=ra.response,
                    response_b=rb.response,
                    model_a=model_a,
                    model_b=model_b,
                    trust_score_a=round(adj_a, 2),
                    trust_score_b=round(adj_b, 2),
                    winner=winner,
                    pii_detected_a=pii_a,
                    pii_detected_b=pii_b,
                    hallucination_risk_a=round(hall_a, 4),
                    hallucination_risk_b=round(hall_b, 4),
                )
            )
        return result

    def _evaluate(self, response: str) -> tuple[float, float, bool]:
        """Return (trust_score 0-100, hallucination_risk 0-1, has_pii)."""
        g = self._guardrails.scan(response)
        h = self._hallucination.analyze(response)

        privacy = 0.3 if g.has_pii else 1.0
        security = 0.2 if g.has_toxicity else 1.0
        robustness = max(0.0, 1.0 - h.hallucination_risk)

        trust = self._trust.compute(
            fairness=0.8,
            privacy=privacy,
            security=security,
            robustness=robustness,
            compliance=0.75,
            authenticity=0.85,
        )
        return trust.overall, h.hallucination_risk, g.has_pii
