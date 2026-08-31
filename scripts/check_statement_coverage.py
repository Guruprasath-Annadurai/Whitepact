# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""OpenSSF Gold ``test_statement_coverage90`` gate.

coverage.py's terminal ``Cover`` percentage is blended with branch coverage
when ``--cov-branch`` is enabled. OpenSSF Gold asks specifically for statement
coverage. This checker calculates pure statement coverage from coverage.json:

    covered statements / total statements

Usage after pytest has produced coverage.json:

    python scripts/check_statement_coverage.py --threshold 90 --fail
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage-json", default="coverage.json", type=Path)
    parser.add_argument("--threshold", type=float, default=90.0)
    parser.add_argument("--fail", action="store_true")
    args = parser.parse_args()

    if not args.coverage_json.exists():
        print(
            f"{args.coverage_json} not found -- run pytest with --cov-report=json first.",
            file=sys.stderr,
        )
        return 2

    data = json.loads(args.coverage_json.read_text(encoding="utf-8"))
    totals = data["totals"]
    num_statements = int(totals.get("num_statements", 0))
    covered_lines = int(totals.get("covered_lines", 0))

    if num_statements <= 0:
        print("No executable statements found in coverage report.", file=sys.stderr)
        return 2

    pure_statement_pct = 100.0 * covered_lines / num_statements
    blended_pct = float(totals.get("percent_covered", 0.0))

    print(
        f"Pure statement coverage: {pure_statement_pct:.2f}%  "
        f"({covered_lines}/{num_statements} statements)"
    )
    print(
        f"Blended stmt+branch %:   {blended_pct:.2f}%  "
        "(coverage.py default with branch measurement enabled)"
    )
    print(f"OpenSSF Gold threshold:  {args.threshold:.0f}% pure statement coverage")

    if pure_statement_pct < args.threshold:
        print(f"BELOW THRESHOLD by {args.threshold - pure_statement_pct:.2f} points.")
        return 1 if args.fail else 0

    print("At or above threshold.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
