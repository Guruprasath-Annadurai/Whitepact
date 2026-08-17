"""OpenSSF `dynamic_analysis` criterion: report and (optionally) gate on
*pure* branch coverage — not the blended statement+branch percentage
`coverage.py`'s own terminal report prints when `--cov-branch` is set.

Why this script exists, not just `coverage report`'s own number:
`coverage.py`'s default "Cover" column with branch coverage enabled is
computed as `(covered_lines + covered_branches) / (num_statements + num_branches)`
— a blended metric. OpenSSF's criterion specifically asks for branch
coverage: `covered_branches / num_branches`, isolated from statement
coverage. The two numbers differ meaningfully for this codebase (85%
blended vs. ~73% pure branch, as of the last run this script was
written against) — reporting the blended number as "branch coverage"
would be a real, checkable overclaim.

Usage (after a normal `pytest` run has produced `coverage.json` — see
pyproject.toml's `addopts`, which already includes `--cov-report=json`):

    python scripts/check_branch_coverage.py [--threshold 80] [--fail]

Without `--fail`, this only prints the number (informational — used in
CI today so the real percentage is visible on every run, without
failing builds on a threshold this codebase does not yet meet). Pass
`--fail` once branch coverage has genuinely reached the threshold via
real tests, not by excluding files, to turn this into a hard CI gate.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage-json", default="coverage.json", type=Path)
    parser.add_argument("--threshold", type=float, default=80.0)
    parser.add_argument(
        "--fail",
        action="store_true",
        help="Exit non-zero if branch coverage is below --threshold. "
        "Off by default -- see module docstring for why.",
    )
    args = parser.parse_args()

    if not args.coverage_json.exists():
        print(
            f"{args.coverage_json} not found -- run pytest with "
            "--cov-branch --cov-report=json first.",
            file=sys.stderr,
        )
        return 2

    data = json.loads(args.coverage_json.read_text())
    totals = data["totals"]
    num_branches = totals.get("num_branches", 0)
    covered_branches = totals.get("covered_branches", 0)

    if num_branches == 0:
        print("No branches found in the coverage report -- nothing to check.")
        return 0

    pure_branch_pct = 100.0 * covered_branches / num_branches
    blended_pct = totals.get("percent_covered", 0.0)

    print(f"Pure branch coverage:    {pure_branch_pct:.2f}%  ({covered_branches}/{num_branches} branches)")
    print(f"Blended stmt+branch %:   {blended_pct:.2f}%  (coverage.py's own default 'Cover' column -- NOT the same metric)")
    print(f"OpenSSF threshold:       {args.threshold:.0f}% (pure branch coverage)")

    if pure_branch_pct < args.threshold:
        print(f"BELOW THRESHOLD by {args.threshold - pure_branch_pct:.2f} points.")
        if args.fail:
            return 1
    else:
        print("At or above threshold.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
