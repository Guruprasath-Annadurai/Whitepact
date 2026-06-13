"""
Basic usage example for BiasBuster.

Run with your real API key:
    OPENAI_API_KEY=sk-... python examples/basic_usage.py
"""

from __future__ import annotations

import asyncio
import os

from biasbuster import BiasBusterRunner, GenderBiasProbe
from biasbuster.providers import OpenAIProvider
from biasbuster.reporting import JsonReporter


async def main() -> None:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("Set OPENAI_API_KEY to run this example.")
        return

    provider = OpenAIProvider(api_key=api_key, model="gpt-4o-mini")
    runner = BiasBusterRunner(provider=provider)

    suite = await runner.run([
        GenderBiasProbe(threshold=0.20),
    ])

    print(f"Overall score : {suite.overall_score:.4f}")
    print(f"Status        : {'PASSED' if suite.passed else 'FAILED'}")
    print()

    for probe_result in suite.probe_results:
        print(f"Probe: {probe_result.probe_name}")
        print(f"  Severity : {probe_result.severity}")
        print(f"  Score    : {probe_result.overall_score:.4f}")
        print()
        for tr in probe_result.template_results:
            print(f"  [{tr.severity:<8}] {tr.divergence_score:.4f}  {tr.template[:60]}…")
        print()

    JsonReporter().save(suite, path="report.json")
    print("Full report saved to report.json")


if __name__ == "__main__":
    asyncio.run(main())
