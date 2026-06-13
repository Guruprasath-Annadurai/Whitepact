from __future__ import annotations

import pytest

from biasbuster.probes.age_bias import (
    DEFAULT_TEMPLATES,
    VARIANTS,
    AgeBiasProbe,
    _fill_template,
    _neutralize_age,
)
from biasbuster.providers.base import BaseProvider, CompletionRequest, CompletionResponse


class BiasedAgeProvider(BaseProvider):
    """Returns markedly different content based on career stage."""

    _RESPONSES = {
        "early": (
            "Alex is an enthusiastic young professional who shows real promise and brings "
            "abundant energy to the team. They are eager to learn and adapt quickly to new "
            "technologies. With proper mentoring they could develop into a solid contributor. "
            "Their main limitation is limited depth of knowledge and narrow exposure to complex "
            "production systems."
        ),
        "mid": (
            "Alex is a skilled and reliable professional with a strong track record of consistent "
            "delivery. They bring solid technical depth and demonstrated leadership capability. "
            "Their experience navigating complex challenges makes them a trusted, sought-after "
            "voice on the team whose judgment colleagues rely on regularly."
        ),
        "late": (
            "Alex is a seasoned expert whose institutional knowledge and strategic perspective "
            "are unmatched on the team. They bring decades of mentorship, broad organisational "
            "wisdom, and the ability to prevent costly mistakes through pattern recognition. "
            "Their technical relevance remains strong and their strategic contributions are "
            "consistently impactful at the highest level."
        ),
    }
    _DEFAULT = "Alex performed their responsibilities professionally and competently."

    @property
    def name(self) -> str:
        return "mock-age-biased"

    @property
    def model_name(self) -> str:
        return "mock-1.0"

    def __init__(self) -> None:
        self.call_count = 0

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self.call_count += 1
        prompt_lower = request.prompt.lower()
        if "early-career" in prompt_lower or "3 years" in prompt_lower or " 26 " in prompt_lower:
            return CompletionResponse(
                text=self._RESPONSES["early"], model=self.model_name, provider=self.name
            )
        if (
            "late-career" in prompt_lower
            or "34 years" in prompt_lower
            or " 58 " in prompt_lower
            or "veteran professional" in prompt_lower
        ):
            return CompletionResponse(
                text=self._RESPONSES["late"], model=self.model_name, provider=self.name
            )
        return CompletionResponse(
            text=self._RESPONSES["mid"], model=self.model_name, provider=self.name
        )


class NeutralAgeProvider(BaseProvider):
    """Returns structurally identical responses regardless of career stage."""

    _RESPONSE = (
        "Alex is a highly capable professional with a consistent record of excellent delivery. "
        "They bring strong technical skills, clear communication, and genuine commitment to the "
        "work. Their contributions are well-regarded by colleagues and stakeholders alike. "
        "They are a reliable, collaborative team member who consistently meets and exceeds "
        "expectations across every project they take on."
    )

    @property
    def name(self) -> str:
        return "mock-age-neutral"

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


class TestNeutralizeAge:
    def test_strips_age_number(self) -> None:
        result = _neutralize_age("Alex is 26 years old and very capable.")
        assert "26" not in result
        assert "__age__" in result

    def test_strips_early_career_stage(self) -> None:
        result = _neutralize_age("As an early-career professional, Alex brings fresh energy.")
        assert "early-career" not in result
        assert "__age__" in result

    def test_strips_late_career_stage(self) -> None:
        result = _neutralize_age("As a late-career expert, Alex brings deep wisdom.")
        assert "late-career" not in result

    def test_strips_years_of_experience(self) -> None:
        result = _neutralize_age("Alex has 17 years of industry experience.")
        assert "17 years of industry experience" not in result

    def test_strips_veteran_descriptor(self) -> None:
        result = _neutralize_age("Alex is a veteran professional with extensive tenure.")
        assert "veteran professional" not in result

    def test_preserves_unrelated_content(self) -> None:
        result = _neutralize_age("Alex delivers high-quality code and communicates clearly.")
        assert "high-quality code" in result
        assert "communicates clearly" in result

    def test_lowercases_output(self) -> None:
        result = _neutralize_age("Alex Is A GREAT Engineer.")
        assert result == result.lower()


class TestFillTemplate:
    def test_fills_age(self) -> None:
        template = "Alex is {age} years old."
        filled = _fill_template(template, VARIANTS[0])
        assert "26" in filled
        assert "{age}" not in filled

    def test_fills_career_stage(self) -> None:
        template = "A {career_stage} engineer."
        filled = _fill_template(template, VARIANTS[1])
        assert "mid-career" in filled

    def test_fills_descriptor(self) -> None:
        template = "{Name} is a {descriptor}."
        filled = _fill_template(template, VARIANTS[2])
        assert "Alex" in filled
        assert "veteran professional" in filled

    def test_fills_years_experience(self) -> None:
        template = "{name} has {years_experience} years."
        filled = _fill_template(template, VARIANTS[2])
        assert "34" in filled


class TestAgeBiasProbeWithBiasedProvider:
    @pytest.mark.asyncio
    async def test_flags_biased_provider(self) -> None:
        probe = AgeBiasProbe(templates=DEFAULT_TEMPLATES[:3], threshold=0.20)
        result = await probe.run(BiasedAgeProvider())
        assert result.overall_score > 0.20, (
            f"Expected score > 0.20 for biased provider, got {result.overall_score:.4f}"
        )
        assert not result.passed

    @pytest.mark.asyncio
    async def test_template_results_count(self) -> None:
        n = 3
        probe = AgeBiasProbe(templates=DEFAULT_TEMPLATES[:n])
        result = await probe.run(BiasedAgeProvider())
        assert len(result.template_results) == n

    @pytest.mark.asyncio
    async def test_each_template_has_three_variants(self) -> None:
        probe = AgeBiasProbe(templates=DEFAULT_TEMPLATES[:1])
        result = await probe.run(BiasedAgeProvider())
        assert len(result.template_results[0].variant_responses) == 3
        names = {vr.variant_name for vr in result.template_results[0].variant_responses}
        assert names == {"early_career", "mid_career", "late_career"}

    @pytest.mark.asyncio
    async def test_most_divergent_pair_populated(self) -> None:
        probe = AgeBiasProbe(templates=DEFAULT_TEMPLATES[:2])
        result = await probe.run(BiasedAgeProvider())
        for tr in result.template_results:
            assert tr.most_divergent_pair is not None

    @pytest.mark.asyncio
    async def test_confidence_interval_populated(self) -> None:
        probe = AgeBiasProbe(templates=DEFAULT_TEMPLATES[:3])
        result = await probe.run(BiasedAgeProvider())
        assert result.confidence_interval is not None
        lo, hi = result.confidence_interval
        assert lo <= hi

    @pytest.mark.asyncio
    async def test_provider_call_count(self) -> None:
        n_templates = 3
        n_variants = 3
        provider = BiasedAgeProvider()
        probe = AgeBiasProbe(templates=DEFAULT_TEMPLATES[:n_templates])
        await probe.run(provider)
        assert provider.call_count == n_templates * n_variants

    @pytest.mark.asyncio
    async def test_score_bounded(self) -> None:
        probe = AgeBiasProbe(templates=DEFAULT_TEMPLATES[:2])
        result = await probe.run(BiasedAgeProvider())
        assert 0.0 <= result.overall_score <= 1.0
        for tr in result.template_results:
            assert 0.0 <= tr.divergence_score <= 1.0

    @pytest.mark.asyncio
    async def test_metadata_variant_names(self) -> None:
        probe = AgeBiasProbe(templates=DEFAULT_TEMPLATES[:1])
        result = await probe.run(BiasedAgeProvider())
        assert result.metadata["variant_names"] == ["early_career", "mid_career", "late_career"]

    @pytest.mark.asyncio
    async def test_worst_template_populated(self) -> None:
        probe = AgeBiasProbe(templates=DEFAULT_TEMPLATES[:3])
        result = await probe.run(BiasedAgeProvider())
        assert result.metadata["worst_template"] is not None


class TestAgeBiasProbeWithNeutralProvider:
    @pytest.mark.asyncio
    async def test_passes_neutral_provider(self) -> None:
        probe = AgeBiasProbe(templates=DEFAULT_TEMPLATES[:3], threshold=0.20)
        result = await probe.run(NeutralAgeProvider())
        assert result.passed, (
            f"Expected neutral provider to pass, got score {result.overall_score:.4f}"
        )

    @pytest.mark.asyncio
    async def test_low_score_for_neutral(self) -> None:
        probe = AgeBiasProbe(templates=DEFAULT_TEMPLATES[:3])
        result = await probe.run(NeutralAgeProvider())
        assert result.overall_score < 0.10


class TestAgeBiasProbeResultShape:
    @pytest.mark.asyncio
    async def test_probe_name(self) -> None:
        probe = AgeBiasProbe(templates=DEFAULT_TEMPLATES[:1])
        result = await probe.run(NeutralAgeProvider())
        assert result.probe_name == "age-bias"

    @pytest.mark.asyncio
    async def test_to_dict_serialisable(self) -> None:
        import json

        probe = AgeBiasProbe(templates=DEFAULT_TEMPLATES[:1])
        result = await probe.run(NeutralAgeProvider())
        assert isinstance(json.dumps(result.to_dict()), str)

    @pytest.mark.asyncio
    async def test_custom_threshold(self) -> None:
        provider = BiasedAgeProvider()
        strict = AgeBiasProbe(templates=DEFAULT_TEMPLATES[:2], threshold=0.001)
        lenient = AgeBiasProbe(templates=DEFAULT_TEMPLATES[:2], threshold=0.999)
        assert not (await strict.run(provider)).passed
        assert (await lenient.run(provider)).passed
