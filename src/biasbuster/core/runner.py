from __future__ import annotations

import asyncio
from collections.abc import Sequence

from biasbuster.core.base_probe import BaseProbe
from biasbuster.core.result import SuiteResult
from biasbuster.providers.base import BaseProvider


class BiasBusterRunner:
    """
    Orchestrates running one or more probes against a provider.

    Usage::

        runner = BiasBusterRunner(provider=OpenAIProvider(api_key="..."))
        suite = await runner.run([GenderBiasProbe(), RacialBiasProbe()])
        print(suite.overall_score)
    """

    def __init__(
        self,
        provider: BaseProvider,
        *,
        concurrency: int = 3,
    ) -> None:
        self._provider = provider
        self._concurrency = concurrency

    async def run(self, probes: Sequence[BaseProbe]) -> SuiteResult:
        """Run all probes, respecting the concurrency limit."""
        semaphore = asyncio.Semaphore(self._concurrency)

        async def _run_one(probe: BaseProbe):  # type: ignore[return]
            async with semaphore:
                return await probe.run(self._provider)

        probe_results = await asyncio.gather(*[_run_one(p) for p in probes])

        return SuiteResult(
            provider_name=self._provider.name,
            model_name=self._provider.model_name,
            probe_results=list(probe_results),
        )

    async def run_one(self, probe: BaseProbe) -> SuiteResult:
        return await self.run([probe])
