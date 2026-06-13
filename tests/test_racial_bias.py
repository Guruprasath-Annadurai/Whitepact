from __future__ import annotations

import pytest

from biasbuster.probes.racial_bias import DEFAULT_TEMPLATES, ETHNIC_GROUPS, RacialBiasProbe
from biasbuster.providers.base import BaseProvider, CompletionRequest, CompletionResponse


class BiasedRacialProvider(BaseProvider):
    """Returns markedly different content per ethnic group name."""

    _RESPONSES = {
        "Emily": (
            "Emily demonstrates exceptional leadership, strategic vision, and technical depth. "
            "She is a highly articulate communicator who consistently exceeds expectations "
            "and earns the trust of senior stakeholders with her polished, professional approach."
        ),
        "Lakisha": (
            "Lakisha is a decent worker who generally meets basic requirements. "
            "She gets along okay with the team and shows up reliably most of the time."
        ),
        "Maria": (
            "Maria is hardworking and puts in a lot of effort. "
            "She tries her best and the team likes working with her."
        ),
        "Wei": (
            "Wei is technically proficient and detail-oriented. "
            "She is quiet but delivers solid work and rarely makes mistakes."
        ),
    }
    _DEFAULT = "The subject completed their assigned work satisfactorily."

    @property
    def name(self) -> str:
        return "mock-racial-biased"

    @property
    def model_name(self) -> str:
        return "mock-1.0"

    def __init__(self) -> None:
        self.call_count = 0

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self.call_count += 1
        for name, response in self._RESPONSES.items():
            if name in request.prompt:
                return CompletionResponse(text=response, model=self.model_name, provider=self.name)
        return CompletionResponse(text=self._DEFAULT, model=self.model_name, provider=self.name)


class UnbiasedRacialProvider(BaseProvider):
    """Returns structurally identical responses regardless of name."""

    _TEMPLATE = (
        "{name} is a highly capable professional with a strong track record. "
        "They consistently deliver excellent results, collaborate effectively with their team, "
        "and demonstrate clear technical and leadership skills. "
        "Their contributions have had a measurable positive impact on the organisation."
    )

    @property
    def name(self) -> str:
        return "mock-racial-unbiased"

    @property
    def model_name(self) -> str:
        return "mock-1.0"

    def __init__(self) -> None:
        self.call_count = 0

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self.call_count += 1
        for group_names in ETHNIC_GROUPS.values():
            for n in group_names:
                if n in request.prompt:
                    return CompletionResponse(
                        text=self._TEMPLATE.format(name=n),
                        model=self.model_name,
                        provider=self.name,
                    )
        return CompletionResponse(
            text=self._TEMPLATE.format(name="the subject"),
            model=self.model_name,
            provider=self.name,
        )


class TestRacialBiasProbeWithBiasedProvider:
    @pytest.mark.asyncio
    async def test_flags_biased_provider(self) -> None:
        probe = RacialBiasProbe(templates=DEFAULT_TEMPLATES[:3], threshold=0.20)
        result = await probe.run(BiasedRacialProvider())
        assert result.overall_score > 0.20, (
            f"Expected score > 0.20 for biased provider, got {result.overall_score:.4f}"
        )
        assert not result.passed

    @pytest.mark.asyncio
    async def test_template_results_count(self) -> None:
        n = 3
        probe = RacialBiasProbe(templates=DEFAULT_TEMPLATES[:n])
        result = await probe.run(BiasedRacialProvider())
        assert len(result.template_results) == n

    @pytest.mark.asyncio
    async def test_each_template_has_four_groups(self) -> None:
        probe = RacialBiasProbe(templates=DEFAULT_TEMPLATES[:1])
        result = await probe.run(BiasedRacialProvider())
        variant_names = {vr.variant_name for vr in result.template_results[0].variant_responses}
        assert variant_names == {"white", "black", "hispanic", "asian"}

    @pytest.mark.asyncio
    async def test_metadata_groups_listed(self) -> None:
        probe = RacialBiasProbe(templates=DEFAULT_TEMPLATES[:2])
        result = await probe.run(BiasedRacialProvider())
        assert "groups_tested" in result.metadata
        assert set(result.metadata["groups_tested"]) == {"white", "black", "hispanic", "asian"}

    @pytest.mark.asyncio
    async def test_citation_in_metadata(self) -> None:
        probe = RacialBiasProbe(templates=DEFAULT_TEMPLATES[:1])
        result = await probe.run(BiasedRacialProvider())
        assert "Bertrand" in result.metadata.get("citation", "")

    @pytest.mark.asyncio
    async def test_most_divergent_pair_populated(self) -> None:
        probe = RacialBiasProbe(templates=DEFAULT_TEMPLATES[:2])
        result = await probe.run(BiasedRacialProvider())
        for tr in result.template_results:
            assert tr.most_divergent_pair is not None

    @pytest.mark.asyncio
    async def test_confidence_interval_populated(self) -> None:
        probe = RacialBiasProbe(templates=DEFAULT_TEMPLATES[:3])
        result = await probe.run(BiasedRacialProvider())
        assert result.confidence_interval is not None
        lo, hi = result.confidence_interval
        assert lo <= hi

    @pytest.mark.asyncio
    async def test_provider_called_correct_number_of_times(self) -> None:
        n_templates = 3
        n_groups = 4
        provider = BiasedRacialProvider()
        probe = RacialBiasProbe(templates=DEFAULT_TEMPLATES[:n_templates])
        await probe.run(provider)
        assert provider.call_count == n_templates * n_groups

    @pytest.mark.asyncio
    async def test_score_bounded(self) -> None:
        probe = RacialBiasProbe(templates=DEFAULT_TEMPLATES[:2])
        result = await probe.run(BiasedRacialProvider())
        assert 0.0 <= result.overall_score <= 1.0
        for tr in result.template_results:
            assert 0.0 <= tr.divergence_score <= 1.0


class TestRacialBiasProbeWithUnbiasedProvider:
    @pytest.mark.asyncio
    async def test_passes_unbiased_provider(self) -> None:
        probe = RacialBiasProbe(templates=DEFAULT_TEMPLATES[:3], threshold=0.20)
        result = await probe.run(UnbiasedRacialProvider())
        assert result.passed, (
            f"Expected unbiased provider to pass, got score {result.overall_score:.4f}"
        )

    @pytest.mark.asyncio
    async def test_low_score_for_unbiased(self) -> None:
        probe = RacialBiasProbe(templates=DEFAULT_TEMPLATES[:3])
        result = await probe.run(UnbiasedRacialProvider())
        assert result.overall_score < 0.30


class TestRacialBiasProbeResultShape:
    @pytest.mark.asyncio
    async def test_to_dict_serialisable(self) -> None:
        import json

        probe = RacialBiasProbe(templates=DEFAULT_TEMPLATES[:1])
        result = await probe.run(UnbiasedRacialProvider())
        assert isinstance(json.dumps(result.to_dict()), str)

    @pytest.mark.asyncio
    async def test_probe_name(self) -> None:
        probe = RacialBiasProbe(templates=DEFAULT_TEMPLATES[:1])
        result = await probe.run(UnbiasedRacialProvider())
        assert result.probe_name == "racial-bias"

    @pytest.mark.asyncio
    async def test_custom_threshold(self) -> None:
        provider = BiasedRacialProvider()
        strict = RacialBiasProbe(templates=DEFAULT_TEMPLATES[:2], threshold=0.001)
        lenient = RacialBiasProbe(templates=DEFAULT_TEMPLATES[:2], threshold=0.999)
        assert not (await strict.run(provider)).passed
        assert (await lenient.run(provider)).passed
