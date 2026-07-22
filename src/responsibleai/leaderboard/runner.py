"""LeaderboardRunner — orchestrates one full cross-model evaluation pass.

Deliberately reuses the platform's existing eval engines rather than
building a parallel scoring stack:

    BenchmarkRunner    -> TruthfulQA (factual accuracy), BBQ (bias rate),
                           HellaSwag (commonsense consistency)
    RedTeamSimulator   -> adversarial/jailbreak resistance (security)
    GuardrailsEngine   -> PII leakage across every live response (privacy)
    HallucinationDetector -> hedging/unsupported-claim risk (robustness)
    TrustScoreEngine   -> the final weighted composite score/grade

Dimension mapping — stated honestly, matching this platform's practice of
not fabricating what isn't actually measured:

    fairness     <- 1 - BBQ bias_rate                        (live)
    privacy      <- 1 - PII-leak rate across all responses    (live)
    security     <- RedTeamSimulator security_score           (live)
    robustness   <- 0.5*TruthfulQA accuracy + 0.5*(1 - avg hallucination risk) (live)
    compliance   <- neutral 0.5 placeholder                   (NOT live-measured)
    authenticity <- neutral 0.5 placeholder                   (NOT live-measured)

`compliance` (regulatory maturity) and `authenticity` (media/deepfake
authenticity) don't have a behavioral analog observable from a single
model's text responses to a prompt corpus — rather than force-fitting a
fake signal, this runner holds them at a disclosed neutral midpoint. See
`dimensions_live` on the result and compliance/LEADERBOARD_METHODOLOGY.md.
"""

from __future__ import annotations

from responsibleai.eval.benchmarks import BenchmarkRunner
from responsibleai.eval.models import BenchmarkSuite
from responsibleai.guardrails.engine import GuardrailsEngine
from responsibleai.hallucination.detector import HallucinationDetector
from responsibleai.leaderboard.models import DiagnosticFinding, LeaderboardRunResult
from responsibleai.leaderboard.providers import ModelAdapter
from responsibleai.redteam.simulator import RedTeamSimulator
from responsibleai.trust.score import TrustScoreEngine

_EXCERPT_MAX_CHARS = 160

_DIMENSIONS_LIVE = {
    "fairness": True,
    "privacy": True,
    "security": True,
    "robustness": True,
    "compliance": False,
    "authenticity": False,
}


def _excerpt(text: str) -> str:
    text = text.strip()
    return text if len(text) <= _EXCERPT_MAX_CHARS else text[: _EXCERPT_MAX_CHARS - 1] + "…"


class LeaderboardRunner:
    """Runs the full evaluation corpus against one model via a ModelAdapter."""

    def __init__(
        self,
        guardrails: GuardrailsEngine | None = None,
        hallucination: HallucinationDetector | None = None,
        benchmark_runner: BenchmarkRunner | None = None,
        redteam: RedTeamSimulator | None = None,
        trust_engine: TrustScoreEngine | None = None,
    ) -> None:
        self._guardrails = guardrails or GuardrailsEngine()
        self._hallucination = hallucination or HallucinationDetector()
        self._benchmark_runner = benchmark_runner or BenchmarkRunner(self._guardrails)
        self._redteam = redteam or RedTeamSimulator()
        self._trust_engine = trust_engine or TrustScoreEngine()

    async def _collect(self, adapter: ModelAdapter, prompts: list[dict[str, str]]) -> dict[str, str]:
        responses: dict[str, str] = {}
        for p in prompts:
            responses[p["id"]] = await adapter.generate(p["prompt"])
        return responses

    async def run_model(self, model: str, provider: str, adapter: ModelAdapter) -> LeaderboardRunResult:
        # 1. Collect live responses for every prompt set.
        tqa_prompts = self._benchmark_runner.get_prompts(BenchmarkSuite.TRUTHFULQA)
        bbq_prompts = self._benchmark_runner.get_prompts(BenchmarkSuite.BBQ)
        hswag_prompts = self._benchmark_runner.get_prompts(BenchmarkSuite.HELLASWAG)
        redteam_payloads = self._redteam.get_attack_payloads()

        tqa_responses = await self._collect(adapter, tqa_prompts)
        bbq_responses = await self._collect(adapter, bbq_prompts)
        hswag_responses = await self._collect(adapter, hswag_prompts)
        redteam_responses = {p["name"]: await adapter.generate(p["payload"]) for p in redteam_payloads}

        # 2. Score each suite with the existing engines.
        tqa_result = self._benchmark_runner.run(model, provider, BenchmarkSuite.TRUTHFULQA, tqa_responses)
        bbq_result = self._benchmark_runner.run(model, provider, BenchmarkSuite.BBQ, bbq_responses)
        hswag_result = self._benchmark_runner.run(model, provider, BenchmarkSuite.HELLASWAG, hswag_responses)
        redteam_report = self._redteam.analyze_responses(model, provider, redteam_responses)

        # 3. Hallucination risk, averaged across every generative (non-bias) response.
        hallucination_texts = list(tqa_responses.values()) + list(hswag_responses.values())
        hallucination_risks = [
            self._hallucination.analyze(text).hallucination_risk
            for text in hallucination_texts
            if text
        ]
        avg_hallucination_risk = (
            sum(hallucination_risks) / len(hallucination_risks) if hallucination_risks else 0.5
        )

        # 4. Privacy: PII-leak rate across every live response collected.
        all_responses = {
            **{f"truthfulqa:{k}": v for k, v in tqa_responses.items()},
            **{f"bbq:{k}": v for k, v in bbq_responses.items()},
            **{f"hellaswag:{k}": v for k, v in hswag_responses.items()},
            **{f"redteam:{k}": v for k, v in redteam_responses.items()},
        }
        guardrail_scans = {key: self._guardrails.scan(text) for key, text in all_responses.items() if text}
        pii_leak_count = sum(1 for r in guardrail_scans.values() if r.has_pii)
        pii_leak_rate = pii_leak_count / len(guardrail_scans) if guardrail_scans else 0.0

        # 5. Compose the six-dimension TrustScore.
        fairness = 1.0 - bbq_result.bias_rate
        privacy = 1.0 - pii_leak_rate
        security = redteam_report.security_score
        robustness = 0.5 * tqa_result.accuracy + 0.5 * (1.0 - min(avg_hallucination_risk, 1.0))
        trust_score = self._trust_engine.compute(
            fairness=fairness,
            privacy=privacy,
            security=security,
            robustness=robustness,
            compliance=0.5,
            authenticity=0.5,
        )

        # 6. Build the diagnostic findings (paid deep-dive content).
        findings: list[DiagnosticFinding] = []
        for r in tqa_result.sample_results:
            if not r.correct:
                findings.append(DiagnosticFinding(
                    suite="truthfulqa", sample_id=r.sample_id, category=r.category or "general",
                    failure_reason="Response did not contain any expected factual keyword — "
                                    "likely repeated a common misconception.",
                    severity="n/a", prompt_excerpt=_excerpt(r.prompt),
                ))
        for r in bbq_result.sample_results:
            if r.bias_detected:
                findings.append(DiagnosticFinding(
                    suite="bbq", sample_id=r.sample_id, category=r.category or "general",
                    failure_reason="Response matched a known bias pattern for this category.",
                    severity="high", prompt_excerpt=_excerpt(r.prompt),
                ))
        for r in hswag_result.sample_results:
            if not r.correct:
                findings.append(DiagnosticFinding(
                    suite="hellaswag", sample_id=r.sample_id, category=r.category or "general",
                    failure_reason="Response didn't match the expected commonsense continuation.",
                    severity="n/a", prompt_excerpt=_excerpt(r.prompt),
                ))
        for attack_result in redteam_report.attack_results:
            if attack_result.is_vulnerable:
                vector = attack_result.vector
                findings.append(DiagnosticFinding(
                    suite="redteam", sample_id=vector.name, category=vector.category.value,
                    failure_reason=f"Vulnerable to {vector.category.value} attack "
                                    f"(signals: {', '.join(attack_result.vulnerability_signals) or 'refusal language absent'}).",
                    severity=attack_result.severity, prompt_excerpt=_excerpt(vector.payload),
                ))
        for key, scan in guardrail_scans.items():
            if scan.has_pii:
                suite, _, sample_id = key.partition(":")
                categories = sorted({f.category for f in scan.pii_findings})
                findings.append(DiagnosticFinding(
                    suite="privacy_scan", sample_id=f"{suite}:{sample_id}", category=", ".join(categories) or "pii",
                    failure_reason="Response contained apparent PII in its output.",
                    severity="high", prompt_excerpt=_excerpt(all_responses[key]),
                ))

        return LeaderboardRunResult(
            model=model,
            provider=provider,
            trust_score=trust_score,
            truthfulqa_accuracy=tqa_result.accuracy,
            bbq_bias_rate=bbq_result.bias_rate,
            hellaswag_accuracy=hswag_result.accuracy,
            security_score=security,
            privacy_pii_leak_rate=pii_leak_rate,
            avg_hallucination_risk=avg_hallucination_risk,
            sample_size=len(all_responses),
            dimensions_live=dict(_DIMENSIONS_LIVE),
            findings=findings,
        )
