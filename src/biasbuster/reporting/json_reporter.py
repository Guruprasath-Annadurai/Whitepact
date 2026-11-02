from __future__ import annotations

import json
from pathlib import Path

from biasbuster.core.result import ProbeResult, SuiteResult


class JsonReporter:
    """
    Serialises probe and suite results to JSON.

    Usage::

        reporter = JsonReporter()
        reporter.print(suite_result)
        reporter.save(suite_result, Path("report.json"))
    """

    def __init__(self, indent: int = 2) -> None:
        self._indent = indent

    def dumps(self, result: SuiteResult | ProbeResult) -> str:
        return json.dumps(result.to_dict(), indent=self._indent, ensure_ascii=False)

    def save(self, result: SuiteResult | ProbeResult, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.dumps(result), encoding="utf-8")

    def print(self, result: SuiteResult | ProbeResult) -> None:
        print(self.dumps(result))
