from __future__ import annotations

import pytest

from biasbuster.probes.religious_bias import (
    DEFAULT_TEMPLATES,
    ReligiousBiasProbe,
    _neutralize_religion,
)
from biasbuster.providers.base import BaseProvider, CompletionRequest, CompletionResponse


class BiasedReligiousProvider(BaseProvider):
    """Returns different quality/length content per religious identity."""

    _RESPONSES = {
        "Christian": (
            "Alex is an exemplary professional who consistently demonstrates integrity, "
            "collaboration, and a strong work ethic. Their contributions are thoughtful and "
            "well-considered. Colleagues and stakeholders across the organisation hold Alex in "
            "the highest regard for their polished, principled approach to every challenge."
        ),
        "Muslim": (
            "Alex is a dedicated worker who generally meets expectations. "
            "They are professional and get along reasonably well with the team."
        ),
        "Jewish": (
            "Alex is a sharp, analytical thinker with strong attention to detail and intellectual "
            "rigour. They bring deep technical expertise and a methodical problem-solving approach "
            "that is highly valued by the engineering organisation."
        ),
        "Hindu": (
            "Alex is a hardworking and diligent professional who completes assigned tasks "
            "reliably. They contribute positively to the team culture and are well-liked "
            "by their immediate colleagues."
        ),
        "non-religious": (
            "Alex is a technically strong, pragmatic professional with a focus on measurable "
            "outcomes. Their data-driven decision-making and clear communication make them a "
            "consistent contributor to the team's delivery objectives."
        ),
    }
    _DEFAULT = "Alex performed their assigned work satisfactorily."

    @property
    def name(self) -> str:
        return "mock-religious-biased"

    @property
    def model_name(self) -> str:
        return "mock-1.0"

    def __init__(self) -> None:
        self.call_count = 0

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self.call_count += 1
        for label, response in self._RESPONSES.items():
            if label in request.prompt:
                return CompletionResponse(
                    text=response, model=self.model_name, provider=self.name
                )
        return CompletionResponse(
            text=self._DEFAULT, model=self.model_name, provider=self.name
        )


class UnbiasedReligiousProvider(BaseProvider):
    """Returns structurally identical responses regardless of religious identity."""

    _RESPONSE = (
        "Alex is a skilled and respected professional who brings consistent value to every team. "
        "They communicate clearly, collaborate effectively, and deliver high-quality work. "
        "Their problem-solving approach is methodical and their interpersonal skills are strong. "
        "Colleagues and stakeholders alike describe Alex as reliable, thoughtful, and impactful."
    )

    @property
    def name(self) -> str:
        return "mock-religious-unbiased"

    @property
    def model_name(self) -> str:
        return "mock-1.0"

    def __init__(self) -> None:
        self.call_count = 0

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self.call_count += 1
        return CompletionResponse(
            text=self._RESPONSE, model=self.model_name, provider=self.name
        )


class TestNeutralizeReligion:
    def test_strips_christian(self) -> None:
        result = _neutralize_religion("Alex, who is Christian, joined the company.")
        assert "christian" not in result.lower()
        assert "__religion__" in result

    def test_strips_muslim(self) -> None:
        result = _neutralize_religion("Alex is a Muslim professional.")
        assert "muslim" not in result.lower()

    def test_strips_jewish(self) -> None:
        result = _neutralize_religion("Alex, who is Jewish, leads the team.")
        assert "jewish" not in result.lower()

    def test_strips_faith_words(self) -> None:
        result = _neutralize_religion("Their faith and prayer life inform their decisions.")
        assert "faith" not in result
        assert "prayer" not in result

    def test_strips_place_of_worship(self) -> None:
        result = _neutralize_religion("They attend mosque and synagogue regularly.")
        assert "mosque" not in result
        assert "synagogue" not in result

    def test_preserves_professional_content(self) -> None:
        result = _neutralize_religion("Alex delivers excellent software and mentors colleagues.")
        assert "excellent software" in result
        assert "mentors colleagues" in result

    def test_lowercases_output(self) -> None:
        result = _neutralize_religion("Alex Is A GREAT Engineer.")
        assert result == result.lower()


class TestReligiousBiasProbeWithBiasedProvider:
    @pytest.mark.asyncio
    async def test_flags_biased_provider(self) -> None:
        probe = ReligiousBiasProbe(templates=DEFAULT_TEMPLATES[:3], threshold=0.20)
        result = await probe.run(BiasedReligiousProvider())
        assert result.overall_score > 0.20, (
            f"Expected score > 0.20 for biased provider, got {result.overall_score:.4f}"
        )
        assert not result.passed

    @pytest.mark.asyncio
    async def test_template_results_count(self) -> None:
        n = 3
        probe = ReligiousBiasProbe(templates=DEFAULT_TEMPLATES[:n])
        result = await probe.run(BiasedReligiousProvider())
        assert len(result.template_results) == n

    @pytest.mark.asyncio
    async def test_each_template_has_five_groups(self) -> None:
        probe = ReligiousBiasProbe(templates=DEFAULT_TEMPLATES[:1])
        result = await probe.run(BiasedReligiousProvider())
        variant_names = {vr.variant_name for vr in result.template_results[0].variant_responses}
        assert variant_names == {"christian", "muslim", "jewish", "hindu", "secular"}

    @pytest.mark.asyncio
    async def test_metadata_groups_listed(self) -> None:
        probe = ReligiousBiasProbe(templates=DEFAULT_TEMPLATES[:1])
        result = await probe.run(BiasedReligiousProvider())
        assert "groups_tested" in result.metadata
        assert set(result.metadata["groups_tested"]) == {
            "christian", "muslim", "jewish", "hindu", "secular"
        }

    @pytest.mark.asyncio
    async def test_most_divergent_pair_populated(self) -> None:
        probe = ReligiousBiasProbe(templates=DEFAULT_TEMPLATES[:2])
        result = await probe.run(BiasedReligiousProvider())
        for tr in result.template_results:
            assert tr.most_divergent_pair is not None

    @pytest.mark.asyncio
    async def test_confidence_interval_populated(self) -> None:
        probe = ReligiousBiasProbe(templates=DEFAULT_TEMPLATES[:3])
        result = await probe.run(BiasedReligiousProvider())
        assert result.confidence_interval is not None
        lo, hi = result.confidence_interval
        assert lo <= hi

    @pytest.mark.asyncio
    async def test_provider_call_count(self) -> None:
        n_templates = 2
        n_groups = 5
        provider = BiasedReligiousProvider()
        probe = ReligiousBiasProbe(templates=DEFAULT_TEMPLATES[:n_templates])
        await probe.run(provider)
        assert provider.call_count == n_templates * n_groups

    @pytest.mark.asyncio
    async def test_score_bounded(self) -> None:
        probe = ReligiousBiasProbe(templates=DEFAULT_TEMPLATES[:2])
        result = await probe.run(BiasedReligiousProvider())
        assert 0.0 <= result.overall_score <= 1.0
        for tr in result.template_results:
            assert 0.0 <= tr.divergence_score <= 1.0


class TestReligiousBiasProbeWithUnbiasedProvider:
    @pytest.mark.asyncio
    async def test_passes_unbiased_provider(self) -> None:
        probe = ReligiousBiasProbe(templates=DEFAULT_TEMPLATES[:3], threshold=0.20)
        result = await probe.run(UnbiasedReligiousProvider())
        assert result.passed, (
            f"Expected unbiased provider to pass, got score {result.overall_score:.4f}"
        )

    @pytest.mark.asyncio
    async def test_low_score_for_unbiased(self) -> None:
        probe = ReligiousBiasProbe(templates=DEFAULT_TEMPLATES[:3])
        result = await probe.run(UnbiasedReligiousProvider())
        assert result.overall_score < 0.10


class TestReligiousBiasProbeResultShape:
    @pytest.mark.asyncio
    async def test_probe_name(self) -> None:
        probe = ReligiousBiasProbe(templates=DEFAULT_TEMPLATES[:1])
        result = await probe.run(UnbiasedReligiousProvider())
        assert result.probe_name == "religious-bias"

    @pytest.mark.asyncio
    async def test_to_dict_serialisable(self) -> None:
        import json

        probe = ReligiousBiasProbe(templates=DEFAULT_TEMPLATES[:1])
        result = await probe.run(UnbiasedReligiousProvider())
        assert isinstance(json.dumps(result.to_dict()), str)

    @pytest.mark.asyncio
    async def test_custom_threshold(self) -> None:
        provider = BiasedReligiousProvider()
        strict = ReligiousBiasProbe(templates=DEFAULT_TEMPLATES[:2], threshold=0.001)
        lenient = ReligiousBiasProbe(templates=DEFAULT_TEMPLATES[:2], threshold=0.999)
        assert not (await strict.run(provider)).passed
        assert (await lenient.run(provider)).passed
