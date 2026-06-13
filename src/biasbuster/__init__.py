"""
BiasBuster — open-source bias testing framework for LLMs.

Quick start::

    from biasbuster import BiasBusterRunner, GenderBiasProbe
    from biasbuster.providers import OpenAIProvider
    import asyncio

    async def main():
        provider = OpenAIProvider(api_key="sk-...")
        runner = BiasBusterRunner(provider=provider)
        suite = await runner.run([GenderBiasProbe()])
        print(suite.overall_score, suite.passed)

    asyncio.run(main())
"""

from biasbuster.core.base_probe import BaseProbe
from biasbuster.core.result import ProbeResult, SuiteResult
from biasbuster.core.runner import BiasBusterRunner
from biasbuster.probes.gender_bias import GenderBiasProbe

__version__ = "0.1.0"
__all__ = [
    "BaseProbe",
    "BiasBusterRunner",
    "GenderBiasProbe",
    "ProbeResult",
    "SuiteResult",
    "__version__",
]
