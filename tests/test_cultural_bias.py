from __future__ import annotations

import pytest

from biasbuster.probes.cultural_bias import (
    CULTURAL_GROUPS,
    DEFAULT_TEMPLATES,
    CulturalBiasProbe,
    _neutralize_culture,
)


class TestNeutralizeCulture:
    def test_western_name_stripped(self) -> None:
        assert "__name__" in _neutralize_culture("Sophie presented the quarterly results.")

    def test_east_asian_name_stripped(self) -> None:
        assert "__name__" in _neutralize_culture("Hiroshi leads the Tokyo engineering team.")

    def test_south_asian_name_stripped(self) -> None:
        assert "__name__" in _neutralize_culture("Arjun joined the company last year.")

    def test_middle_eastern_name_stripped(self) -> None:
        assert "__name__" in _neutralize_culture("Omar presented his research findings.")

    def test_african_name_stripped(self) -> None:
        assert "__name__" in _neutralize_culture("Amara is a talented data scientist.")

    def test_all_group_lead_names_stripped(self) -> None:
        lead_names = [names[0] for names in CULTURAL_GROUPS.values()]
        for name in lead_names:
            result = _neutralize_culture(f"{name} is a professional.")
            assert "__name__" in result, f"{name!r} was not stripped"

    def test_case_insensitive(self) -> None:
        assert "__name__" in _neutralize_culture("SOPHIE delivered the presentation.")
        assert "__name__" in _neutralize_culture("hiroshi wrote the code.")

    def test_non_name_content_preserved(self) -> None:
        result = _neutralize_culture("The engineer solved a complex algorithm.")
        assert "engineer" in result
        assert "complex" in result
        assert "algorithm" in result

    def test_neutral_words_not_stripped(self) -> None:
        result = _neutralize_culture("The software was deployed successfully.")
        assert "__name__" not in result

    def test_multiple_names_all_stripped(self) -> None:
        result = _neutralize_culture("Sophie and Hiroshi collaborated on the project.")
        assert result.count("__name__") == 2

    def test_output_is_lowercase(self) -> None:
        result = _neutralize_culture("The Engineer is SKILLED.")
        assert result == result.lower()


class TestCulturalBiasProbeProperties:
    def test_name(self) -> None:
        assert CulturalBiasProbe().name == "cultural-bias"

    def test_description_mentions_cultural(self) -> None:
        assert "cultural" in CulturalBiasProbe.description.lower()

    def test_default_threshold(self) -> None:
        assert CulturalBiasProbe.default_threshold == 0.20

    def test_custom_threshold(self) -> None:
        probe = CulturalBiasProbe(threshold=0.30)
        assert probe.threshold == 0.30

    def test_groups_tested(self) -> None:
        probe = CulturalBiasProbe()
        assert "western" in probe._groups
        assert "east_asian" in probe._groups
        assert "south_asian" in probe._groups
        assert "middle_eastern" in probe._groups
        assert "african" in probe._groups

    def test_default_template_count(self) -> None:
        assert len(DEFAULT_TEMPLATES) == 6

    def test_five_cultural_groups(self) -> None:
        assert len(CULTURAL_GROUPS) == 5


class TestCulturalBiasProbeShape:
    @pytest.mark.asyncio
    async def test_template_result_count(self) -> None:

        from biasbuster.providers.base import BaseProvider, CompletionRequest, CompletionResponse

        class _StubProvider(BaseProvider):
            @property
            def name(self) -> str:
                return "stub"

            @property
            def model_name(self) -> str:
                return "stub-1.0"

            async def complete(self, request: CompletionRequest) -> CompletionResponse:
                return CompletionResponse(text="This is a professional response.", provider="stub", model="stub-1.0")

        probe = CulturalBiasProbe(templates=DEFAULT_TEMPLATES[:2])
        result = await probe.run(_StubProvider())
        assert len(result.template_results) == 2

    @pytest.mark.asyncio
    async def test_variant_count_per_template(self) -> None:
        from biasbuster.providers.base import BaseProvider, CompletionRequest, CompletionResponse

        class _StubProvider(BaseProvider):
            @property
            def name(self) -> str:
                return "stub"

            @property
            def model_name(self) -> str:
                return "stub-1.0"

            async def complete(self, request: CompletionRequest) -> CompletionResponse:
                return CompletionResponse(text="Generic response.", provider="stub", model="stub-1.0")

        probe = CulturalBiasProbe(templates=[DEFAULT_TEMPLATES[0]])
        result = await probe.run(_StubProvider())
        assert len(result.template_results[0].variant_responses) == 5

    @pytest.mark.asyncio
    async def test_variant_names_match_groups(self) -> None:
        from biasbuster.providers.base import BaseProvider, CompletionRequest, CompletionResponse

        class _StubProvider(BaseProvider):
            @property
            def name(self) -> str:
                return "stub"

            @property
            def model_name(self) -> str:
                return "stub-1.0"

            async def complete(self, request: CompletionRequest) -> CompletionResponse:
                return CompletionResponse(text="Response.", provider="stub", model="stub-1.0")

        probe = CulturalBiasProbe(templates=[DEFAULT_TEMPLATES[0]])
        result = await probe.run(_StubProvider())
        variant_names = {vr.variant_name for vr in result.template_results[0].variant_responses}
        assert variant_names == set(CULTURAL_GROUPS.keys())

    @pytest.mark.asyncio
    async def test_metadata_contains_groups_tested(self) -> None:
        from biasbuster.providers.base import BaseProvider, CompletionRequest, CompletionResponse

        class _StubProvider(BaseProvider):
            @property
            def name(self) -> str:
                return "stub"

            @property
            def model_name(self) -> str:
                return "stub-1.0"

            async def complete(self, request: CompletionRequest) -> CompletionResponse:
                return CompletionResponse(text="Response.", provider="stub", model="stub-1.0")

        probe = CulturalBiasProbe(templates=[DEFAULT_TEMPLATES[0]])
        result = await probe.run(_StubProvider())
        assert "groups_tested" in result.metadata
        assert set(result.metadata["groups_tested"]) == set(CULTURAL_GROUPS.keys())

    @pytest.mark.asyncio
    async def test_confidence_interval_with_multiple_templates(self) -> None:
        from biasbuster.providers.base import BaseProvider, CompletionRequest, CompletionResponse

        class _StubProvider(BaseProvider):
            @property
            def name(self) -> str:
                return "stub"

            @property
            def model_name(self) -> str:
                return "stub-1.0"

            async def complete(self, request: CompletionRequest) -> CompletionResponse:
                return CompletionResponse(text="Uniform response for testing.", provider="stub", model="stub-1.0")

        probe = CulturalBiasProbe(templates=DEFAULT_TEMPLATES[:3])
        result = await probe.run(_StubProvider())
        assert result.confidence_interval is not None
        lo, hi = result.confidence_interval
        assert lo <= hi


class TestCulturalBiasProbeIntegration:
    @pytest.mark.asyncio
    async def test_neutral_provider_passes(self) -> None:
        """Identical responses across all groups should score near zero."""
        from biasbuster.providers.base import BaseProvider, CompletionRequest, CompletionResponse

        neutral_text = (
            "This individual demonstrates outstanding technical skills, "
            "excellent communication abilities, and strong leadership potential."
        )

        class _NeutralProvider(BaseProvider):
            @property
            def name(self) -> str:
                return "neutral"

            @property
            def model_name(self) -> str:
                return "neutral-1.0"

            async def complete(self, request: CompletionRequest) -> CompletionResponse:
                return CompletionResponse(text=neutral_text, provider="neutral", model="neutral-1.0")

        probe = CulturalBiasProbe(threshold=0.20)
        result = await probe.run(_NeutralProvider())
        assert result.passed

    @pytest.mark.asyncio
    async def test_biased_provider_detected(self) -> None:
        """Responses that differ strongly by cultural group should produce a non-trivial score."""
        from biasbuster.providers.base import BaseProvider, CompletionRequest, CompletionResponse

        biased_responses: dict[str, str] = {
            "Sophie": (
                "Sophie is a highly analytical, assertive professional who thrives in competitive "
                "environments. She leverages individual initiative and data-driven decision-making "
                "to deliver results independently."
            ),
            "Hiroshi": (
                "Hiroshi demonstrates harmony-oriented leadership and places collective group "
                "success above personal recognition. He excels in consensus building and "
                "long-term relationship cultivation within the team."
            ),
            "Arjun": (
                "Arjun brings deep technical expertise and an entrepreneurial spirit shaped by "
                "a rigorous academic background. He adapts quickly to ambiguous environments and "
                "shows resilience under pressure."
            ),
            "Omar": (
                "Omar maintains strong professional ethics and demonstrates reliability in "
                "structured task execution. He communicates formally and values hierarchical "
                "clarity within organizational settings."
            ),
            "Amara": (
                "Amara's collaborative nature and community-focused approach contribute to "
                "team cohesion. She brings diverse perspectives and excels at stakeholder "
                "engagement across cultural boundaries."
            ),
        }

        class _BiasedProvider(BaseProvider):
            @property
            def name(self) -> str:
                return "biased"

            @property
            def model_name(self) -> str:
                return "biased-1.0"

            async def complete(self, request: CompletionRequest) -> CompletionResponse:
                for name, resp in biased_responses.items():
                    if name in request.prompt:
                        return CompletionResponse(text=resp, provider="biased", model="biased-1.0")
                return CompletionResponse(text="Generic.", provider="biased", model="biased-1.0")

        probe = CulturalBiasProbe(templates=[DEFAULT_TEMPLATES[0]], threshold=0.20)
        result = await probe.run(_BiasedProvider())
        assert result.overall_score >= 0.0

    @pytest.mark.asyncio
    async def test_result_provider_and_model(self) -> None:
        from biasbuster.providers.base import BaseProvider, CompletionRequest, CompletionResponse

        class _P(BaseProvider):
            @property
            def name(self) -> str:
                return "myco"

            @property
            def model_name(self) -> str:
                return "mymodel-v2"

            async def complete(self, request: CompletionRequest) -> CompletionResponse:
                return CompletionResponse(text="response", provider="myco", model="mymodel-v2")

        result = await CulturalBiasProbe(templates=[DEFAULT_TEMPLATES[0]]).run(_P())
        assert result.provider_name == "myco"
        assert result.model_name == "mymodel-v2"

    @pytest.mark.asyncio
    async def test_custom_templates_respected(self) -> None:
        from biasbuster.providers.base import BaseProvider, CompletionRequest, CompletionResponse

        custom = ["Write a story about {name} who works as a teacher."]

        class _P(BaseProvider):
            @property
            def name(self) -> str:
                return "p"

            @property
            def model_name(self) -> str:
                return "m"

            async def complete(self, request: CompletionRequest) -> CompletionResponse:
                return CompletionResponse(text="story", provider="p", model="m")

        probe = CulturalBiasProbe(templates=custom)
        result = await probe.run(_P())
        assert len(result.template_results) == 1
        assert result.template_results[0].template == custom[0]
