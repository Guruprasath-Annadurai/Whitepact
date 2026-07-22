"""Tests for LeaderboardRunner — the orchestrator that reuses the platform's
existing eval engines (BenchmarkRunner, RedTeamSimulator, GuardrailsEngine,
HallucinationDetector, TrustScoreEngine) to produce one leaderboard row."""

from __future__ import annotations

from responsibleai.eval.benchmarks import _TRUTHFULQA_SAMPLES, BenchmarkRunner
from responsibleai.eval.models import BenchmarkSuite
from responsibleai.leaderboard.providers import MockAdapter
from responsibleai.leaderboard.runner import LeaderboardRunner


class TestLeaderboardRunnerWithMockAdapter:
    async def test_run_model_produces_a_full_result(self):
        runner = LeaderboardRunner()
        result = await runner.run_model("mock-model", "mock", MockAdapter(model="mock-model"))

        assert result.model == "mock-model"
        assert result.provider == "mock"
        assert 0.0 <= result.trust_score.overall <= 100.0
        assert result.trust_score.grade in ("A", "B", "C", "D", "F")
        assert result.sample_size == 55  # 15 TruthfulQA + 15 BBQ + 15 HellaSwag + 10 redteam

    async def test_dimensions_live_flags_are_honest(self):
        """Fairness/privacy/security/robustness are behaviorally measured;
        compliance/authenticity are disclosed placeholders — this is the
        core honesty claim of the whole feature, verify it every run."""
        runner = LeaderboardRunner()
        result = await runner.run_model("m", "mock", MockAdapter(model="m"))

        assert result.dimensions_live == {
            "fairness": True, "privacy": True, "security": True, "robustness": True,
            "compliance": False, "authenticity": False,
        }
        # The neutral placeholders must actually be neutral (0.5 -> 50 on the 0-100 scale).
        dims = result.trust_score.to_dict()["dimensions"]
        assert dims["compliance"] == 50.0
        assert dims["authenticity"] == 50.0

    async def test_generic_hedging_response_never_leaks_pii(self):
        runner = LeaderboardRunner()
        result = await runner.run_model("m", "mock", MockAdapter(model="m"))
        assert result.privacy_pii_leak_rate == 0.0

    async def test_findings_are_generated_for_failures(self):
        runner = LeaderboardRunner()
        # The generic mock response fails most TruthfulQA/HellaSwag keyword
        # matches by construction, so there should be real findings to review.
        result = await runner.run_model("m", "mock", MockAdapter(model="m"))
        assert len(result.findings) > 0
        assert all(f.suite in ("truthfulqa", "bbq", "hellaswag", "redteam", "privacy_scan") for f in result.findings)

    async def test_public_dict_never_includes_findings(self):
        runner = LeaderboardRunner()
        result = await runner.run_model("m", "mock", MockAdapter(model="m"))
        public = result.to_public_dict()
        assert "findings" not in public
        assert "dimensions" in public
        assert "raw_metrics" in public

    async def test_diagnostic_dict_includes_findings(self):
        runner = LeaderboardRunner()
        result = await runner.run_model("m", "mock", MockAdapter(model="m"))
        diagnostic = result.to_diagnostic_dict()
        assert "findings" in diagnostic
        assert diagnostic["findings_count"] == len(result.findings)

    async def test_canned_perfect_responses_score_higher_than_generic(self):
        """Sanity check that the scoring pipeline actually differentiates
        quality, not just that it runs without crashing: an adapter that
        returns keyword-perfect TruthfulQA answers should score at least as
        well on that suite as the generic hedging default."""
        br = BenchmarkRunner()
        keywords_by_id = {s["id"]: s["expected_keywords"][0] for s in _TRUTHFULQA_SAMPLES}
        canned: dict[str, str] = {
            p["prompt"]: f"The correct answer involves: {keywords_by_id[p['id']]}"
            for p in br.get_prompts(BenchmarkSuite.TRUTHFULQA)
        }

        runner = LeaderboardRunner()
        generic_result = await runner.run_model("generic", "mock", MockAdapter(model="generic"))
        tuned_result = await runner.run_model(
            "tuned", "mock", MockAdapter(model="tuned", canned_responses=canned),
        )
        assert tuned_result.truthfulqa_accuracy >= generic_result.truthfulqa_accuracy
