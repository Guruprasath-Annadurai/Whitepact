from __future__ import annotations

import pytest

from biasbuster.core.result import Severity
from biasbuster.core.scoring import compute_length_ratio_score, compute_pairwise_divergence
from biasbuster.probes._utils import neutralize_text
from biasbuster.probes.gender_bias import (
    DEFAULT_TEMPLATES,
    VARIANTS,
    GenderBiasProbe,
    _fill_template,
)
from tests.conftest import BiasedMockProvider, MockProvider, UnbiasedMockProvider

_neutralize = neutralize_text
_compute_pairwise_divergence = compute_pairwise_divergence
_length_ratio_score = compute_length_ratio_score


# ---------------------------------------------------------------------------
# Unit tests: helper functions
# ---------------------------------------------------------------------------


class TestNeutralize:
    def test_replaces_masculine_name(self) -> None:
        result = _neutralize("James is a great engineer.")
        assert "james" not in result
        assert "__name__" in result

    def test_replaces_feminine_name(self) -> None:
        result = _neutralize("Mary led the project successfully.")
        assert "mary" not in result
        assert "__name__" in result

    def test_replaces_neutral_name(self) -> None:
        result = _neutralize("Alex joined the team last year.")
        assert "alex" not in result

    def test_replaces_he_pronoun(self) -> None:
        result = _neutralize("He is a strong leader.")
        assert " he " not in result
        assert "__pronoun__" in result

    def test_replaces_she_pronoun(self) -> None:
        result = _neutralize("She delivered excellent results.")
        assert " she " not in result

    def test_replaces_possessive(self) -> None:
        result = _neutralize("His technical skills are exceptional.")
        assert " his " not in result

    def test_preserves_unrelated_content(self) -> None:
        result = _neutralize("The distributed system handles 1M requests per second.")
        assert "distributed system" in result
        assert "1m requests" in result


class TestFillTemplate:
    def test_masculine_variant(self) -> None:
        template = "Write a bio for {name}, a senior engineer."
        filled = _fill_template(template, VARIANTS[0])
        assert "James" in filled
        assert "{name}" not in filled

    def test_feminine_variant(self) -> None:
        template = "{Name} is applying for promotion."
        filled = _fill_template(template, VARIANTS[1])
        assert "Mary" in filled

    def test_neutral_pronoun(self) -> None:
        template = "What challenges might {pronoun_subject} face?"
        filled_neutral = _fill_template(template, VARIANTS[2])
        assert "they" in filled_neutral


class TestPairwiseDivergence:
    def test_identical_texts_score_near_zero(self) -> None:
        texts = ["The engineer is highly skilled.", "The engineer is highly skilled."]
        score, _ = _compute_pairwise_divergence(texts)
        assert score < 0.05

    def test_unrelated_texts_score_high(self) -> None:
        texts = [
            "Quantum mechanics describes subatomic particles and wave functions.",
            "The recipe for chocolate cake requires flour sugar butter and eggs.",
            "Football is a sport played with a round ball on a grass field.",
        ]
        score, _ = _compute_pairwise_divergence(texts)
        assert score > 0.5

    def test_single_text_returns_zero(self) -> None:
        score, pairs = _compute_pairwise_divergence(["only one text"])
        assert score == 0.0
        assert pairs == {}

    def test_pair_scores_populated(self) -> None:
        texts = ["alpha beta gamma", "delta epsilon zeta"]
        _, pairs = _compute_pairwise_divergence(texts)
        assert (0, 1) in pairs
        assert 0.0 <= pairs[(0, 1)] <= 1.0

    def test_three_texts_have_three_pairs(self) -> None:
        texts = ["aaa bbb ccc", "ddd eee fff", "ggg hhh iii"]
        _, pairs = _compute_pairwise_divergence(texts)
        assert len(pairs) == 3


class TestLengthRatioScore:
    def test_equal_length_returns_zero(self) -> None:
        responses = ["one two three", "four five six"]
        assert _length_ratio_score(responses) == pytest.approx(0.0)

    def test_extreme_ratio_capped_at_point_two(self) -> None:
        short = "ok"
        long = " ".join(["word"] * 200)
        score = _length_ratio_score([short, long])
        assert score <= 0.2

    def test_empty_responses_return_zero(self) -> None:
        assert _length_ratio_score([]) == 0.0
        assert _length_ratio_score(["", ""]) == 0.0


# ---------------------------------------------------------------------------
# Integration tests: probe against mock providers
# ---------------------------------------------------------------------------


class TestGenderBiasProbeWithBiasedProvider:
    @pytest.mark.asyncio
    async def test_flags_biased_provider(self, biased_provider: BiasedMockProvider) -> None:
        probe = GenderBiasProbe(templates=DEFAULT_TEMPLATES[:3], threshold=0.20)
        result = await probe.run(biased_provider)
        assert result.overall_score > 0.20, (
            f"Expected score > 0.20 for biased provider, got {result.overall_score:.4f}"
        )
        assert not result.passed

    @pytest.mark.asyncio
    async def test_result_metadata_populated(self, biased_provider: BiasedMockProvider) -> None:
        probe = GenderBiasProbe(templates=DEFAULT_TEMPLATES[:2])
        result = await probe.run(biased_provider)
        assert result.metadata["num_templates"] == 2
        assert result.metadata["num_variants"] == 3
        assert "worst_template" in result.metadata
        assert result.metadata["worst_template"] is not None

    @pytest.mark.asyncio
    async def test_template_results_count(self, biased_provider: BiasedMockProvider) -> None:
        n = 3
        probe = GenderBiasProbe(templates=DEFAULT_TEMPLATES[:n])
        result = await probe.run(biased_provider)
        assert len(result.template_results) == n

    @pytest.mark.asyncio
    async def test_each_template_result_has_three_variants(
        self, biased_provider: BiasedMockProvider
    ) -> None:
        probe = GenderBiasProbe(templates=DEFAULT_TEMPLATES[:1])
        result = await probe.run(biased_provider)
        template_result = result.template_results[0]
        assert len(template_result.variant_responses) == 3
        variant_names = {vr.variant_name for vr in template_result.variant_responses}
        assert variant_names == {"masculine", "feminine", "neutral"}

    @pytest.mark.asyncio
    async def test_most_divergent_pair_identified(
        self, biased_provider: BiasedMockProvider
    ) -> None:
        probe = GenderBiasProbe(templates=DEFAULT_TEMPLATES[:2])
        result = await probe.run(biased_provider)
        for tr in result.template_results:
            assert tr.most_divergent_pair is not None
            assert len(tr.most_divergent_pair) == 2

    @pytest.mark.asyncio
    async def test_provider_called_correct_number_of_times(
        self, biased_provider: BiasedMockProvider
    ) -> None:
        n_templates = 3
        n_variants = 3
        probe = GenderBiasProbe(templates=DEFAULT_TEMPLATES[:n_templates])
        await probe.run(biased_provider)
        assert biased_provider.call_count == n_templates * n_variants


class TestGenderBiasProbeWithUnbiasedProvider:
    @pytest.mark.asyncio
    async def test_passes_unbiased_provider(
        self, unbiased_provider: UnbiasedMockProvider
    ) -> None:
        probe = GenderBiasProbe(templates=DEFAULT_TEMPLATES[:3], threshold=0.20)
        result = await probe.run(unbiased_provider)
        assert result.overall_score < 0.25, (
            f"Expected low score for unbiased provider, got {result.overall_score:.4f}"
        )
        assert result.passed


class TestGenderBiasProbeResultShape:
    @pytest.mark.asyncio
    async def test_to_dict_is_serialisable(self, mock_provider: MockProvider) -> None:
        import json

        probe = GenderBiasProbe(templates=DEFAULT_TEMPLATES[:1])
        result = await probe.run(mock_provider)
        serialised = result.to_dict()
        json_str = json.dumps(serialised)
        assert isinstance(json_str, str)
        assert len(json_str) > 0

    @pytest.mark.asyncio
    async def test_score_bounded(self, biased_provider: BiasedMockProvider) -> None:
        probe = GenderBiasProbe(templates=DEFAULT_TEMPLATES[:2])
        result = await probe.run(biased_provider)
        assert 0.0 <= result.overall_score <= 1.0
        for tr in result.template_results:
            assert 0.0 <= tr.divergence_score <= 1.0

    @pytest.mark.asyncio
    async def test_severity_field_valid(self, biased_provider: BiasedMockProvider) -> None:
        valid: set[Severity] = {"none", "low", "medium", "high", "critical"}
        probe = GenderBiasProbe(templates=DEFAULT_TEMPLATES[:1])
        result = await probe.run(biased_provider)
        assert result.severity in valid

    @pytest.mark.asyncio
    async def test_custom_threshold_respected(self, biased_provider: BiasedMockProvider) -> None:
        probe_strict = GenderBiasProbe(templates=DEFAULT_TEMPLATES[:2], threshold=0.001)
        probe_lenient = GenderBiasProbe(templates=DEFAULT_TEMPLATES[:2], threshold=0.999)

        result_strict = await probe_strict.run(biased_provider)
        result_lenient = await probe_lenient.run(biased_provider)

        assert not result_strict.passed
        assert result_lenient.passed

    @pytest.mark.asyncio
    async def test_probe_name_and_description(self, mock_provider: MockProvider) -> None:
        probe = GenderBiasProbe(templates=DEFAULT_TEMPLATES[:1])
        result = await probe.run(mock_provider)
        assert result.probe_name == "gender-bias"
        assert len(result.probe_description) > 10

    @pytest.mark.asyncio
    async def test_provider_name_captured(self, mock_provider: MockProvider) -> None:
        probe = GenderBiasProbe(templates=DEFAULT_TEMPLATES[:1])
        result = await probe.run(mock_provider)
        assert result.provider_name == "mock"
        assert result.model_name == "mock-1.0"
