"""
BiasBuster — open-source bias testing framework for LLMs.

Quick start::

    from biasbuster import BiasBusterRunner, GenderBiasProbe, RacialBiasProbe
    from biasbuster.providers import OpenAIProvider
    import asyncio

    async def main():
        provider = OpenAIProvider(api_key="sk-...")
        runner = BiasBusterRunner(provider=provider)
        suite = await runner.run([GenderBiasProbe(), RacialBiasProbe()])
        print(suite.overall_score, suite.passed)

    asyncio.run(main())
"""

from biasbuster.core.base_probe import BaseProbe
from biasbuster.core.intersectional import IntersectionalReport, compute_intersectional_report
from biasbuster.core.result import ProbeResult, SuiteResult
from biasbuster.core.runner import BiasBusterRunner
from biasbuster.probes.age_bias import AgeBiasProbe
from biasbuster.probes.cultural_bias import CulturalBiasProbe
from biasbuster.probes.gender_bias import GenderBiasProbe
from biasbuster.probes.occupational_stereotype import OccupationalStereotypeProbe
from biasbuster.probes.racial_bias import RacialBiasProbe
from biasbuster.probes.religious_bias import ReligiousBiasProbe

__version__ = "0.4.0"
__all__ = [
    "AgeBiasProbe",
    "BaseProbe",
    "BiasBusterRunner",
    "CulturalBiasProbe",
    "GenderBiasProbe",
    "IntersectionalReport",
    "OccupationalStereotypeProbe",
    "ProbeResult",
    "RacialBiasProbe",
    "ReligiousBiasProbe",
    "SuiteResult",
    "__version__",
    "compute_intersectional_report",
]
