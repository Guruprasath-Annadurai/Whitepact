from __future__ import annotations

import pytest

from biasbuster.core.runner import BiasBusterRunner
from biasbuster.probes.gender_bias import DEFAULT_TEMPLATES, GenderBiasProbe
from tests.conftest import BiasedMockProvider, MockProvider, UnbiasedMockProvider


class TestBiasBusterRunner:
    @pytest.mark.asyncio
    async def test_run_single_probe(self, mock_provider: MockProvider) -> None:
        probe = GenderBiasProbe(templates=DEFAULT_TEMPLATES[:1])
        runner = BiasBusterRunner(provider=mock_provider)
        suite = await runner.run([probe])
        assert len(suite.probe_results) == 1

    @pytest.mark.asyncio
    async def test_suite_provider_info(self, mock_provider: MockProvider) -> None:
        runner = BiasBusterRunner(provider=mock_provider)
        suite = await runner.run([GenderBiasProbe(templates=DEFAULT_TEMPLATES[:1])])
        assert suite.provider_name == "mock"
        assert suite.model_name == "mock-1.0"

    @pytest.mark.asyncio
    async def test_suite_passed_reflects_all_probes(
        self, unbiased_provider: UnbiasedMockProvider
    ) -> None:
        probes = [
            GenderBiasProbe(templates=DEFAULT_TEMPLATES[:1]),
            GenderBiasProbe(templates=DEFAULT_TEMPLATES[1:2]),
        ]
        runner = BiasBusterRunner(provider=unbiased_provider)
        suite = await runner.run(probes)
        assert suite.passed == all(r.passed for r in suite.probe_results)

    @pytest.mark.asyncio
    async def test_run_one_convenience(self, mock_provider: MockProvider) -> None:
        probe = GenderBiasProbe(templates=DEFAULT_TEMPLATES[:1])
        runner = BiasBusterRunner(provider=mock_provider)
        suite = await runner.run_one(probe)
        assert len(suite.probe_results) == 1

    @pytest.mark.asyncio
    async def test_failed_probes_list(self, biased_provider: BiasedMockProvider) -> None:
        probe = GenderBiasProbe(templates=DEFAULT_TEMPLATES[:2], threshold=0.001)
        runner = BiasBusterRunner(provider=biased_provider)
        suite = await runner.run([probe])
        assert len(suite.failed_probes) == 1

    @pytest.mark.asyncio
    async def test_overall_score_is_mean(self, mock_provider: MockProvider) -> None:
        probes = [GenderBiasProbe(templates=[DEFAULT_TEMPLATES[i]]) for i in range(3)]
        runner = BiasBusterRunner(provider=mock_provider)
        suite = await runner.run(probes)
        expected = sum(r.overall_score for r in suite.probe_results) / len(suite.probe_results)
        assert abs(suite.overall_score - expected) < 1e-9
