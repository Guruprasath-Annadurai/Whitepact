"""
Basic usage example for BiasBuster.

Run with your real API key:
    OPENAI_API_KEY=sk-... python examples/basic_usage.py
"""

from __future__ import annotations

import asyncio
import os

from biasbuster import (
    AgeBiasProbe,
    BiasBusterRunner,
    GenderBiasProbe,
    OccupationalStereotypeProbe,
    RacialBiasProbe,
    ReligiousBiasProbe,
)
from biasbuster.providers import OpenAIProvider
from biasbuster.reporting import HtmlReporter, JsonReporter


async def main() -> None:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("Set OPENAI_API_KEY to run this example.")
        return

    provider = OpenAIProvider(api_key=api_key, model="gpt-4o-mini")
    runner = BiasBusterRunner(provider=provider)

    suite = await runner.run([
        GenderBiasProbe(threshold=0.20),
        RacialBiasProbe(threshold=0.20),
        AgeBiasProbe(threshold=0.20),
        ReligiousBiasProbe(threshold=0.20),
        OccupationalStereotypeProbe(threshold=0.25),
    ])

    print(f"Provider : {suite.provider_name} / {suite.model_name}")
    print(f"Score    : {suite.overall_score:.4f}")
    print(f"Status   : {'PASSED' if suite.passed else 'FAILED'}")
    print()

    for result in suite.probe_results:
        ci_str = ""
        if result.confidence_interval:
            lo, hi = result.confidence_interval
            ci_str = f"  CI [{lo:.3f}, {hi:.3f}]"
        status = "PASS" if result.passed else "FAIL"
        print(f"[{status}] {result.probe_name:<28} score={result.overall_score:.4f}  "
              f"[{result.severity}]{ci_str}")
        for tr in result.template_results:
            pair = f" ({' vs '.join(tr.most_divergent_pair)})" if tr.most_divergent_pair else ""
            print(f"       [{tr.severity:<8}] {tr.divergence_score:.4f}  "
                  f"{tr.template[:60]}…{pair}")
        print()

    JsonReporter().save(suite, "report.json")
    HtmlReporter().save(suite, "report.html")
    print("Reports saved: report.json  report.html")


if __name__ == "__main__":
    asyncio.run(main())
