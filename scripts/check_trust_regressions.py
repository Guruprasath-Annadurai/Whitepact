#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Repository-level guardrails for non-SLSA trust controls.

This intentionally does not duplicate the SLSA-specific release/provenance assertions
enforced by the release tests and evidence register on ``main``.
"""

from __future__ import annotations

import re
from pathlib import Path

REQUIRED = (
    "SECURITY.md",
    "CONTRIBUTING.md",
    ".github/workflows/dco.yml",
    ".github/workflows/dependency-review.yml",
    ".github/workflows/security-scan.yml",
    ".github/workflows/gitleaks.yml",
    "requirements-security.lock",
    "compliance/VULNERABILITY_MANAGEMENT.md",
    "compliance/PUBLIC_TRUST_CLAIMS.md",
)

PROHIBITED_README_CLAIMS = (
    r"\bOpenSSF (?:Best Practices )?Gold (?:certified|achieved|awarded)\b",
    r"\bOSPS (?:Baseline )?(?:L2|L3|Level 2|Level 3) (?:certified|achieved|awarded)\b",
    r"\b(?:ISO(?:/IEC)? 42001|NIST|OWASP|EU AI Act|SOC 2) certified\b",
    r"\bindependently penetration tested\b",
)


def main() -> int:
    failures: list[str] = []
    for name in REQUIRED:
        if not Path(name).is_file():
            failures.append(f"required trust control missing: {name}")

    workflows = "\n".join(
        path.read_text(encoding="utf-8") for path in Path(".github/workflows").glob("*.y*ml")
    )
    if re.search(r"(?m)^\s*pull_request_target\s*:", workflows):
        failures.append("pull_request_target is prohibited without a dedicated threat review")
    if re.search(r"(?m)^\s*permissions\s*:\s*write-all\s*$", workflows):
        failures.append("workflow-level write-all token permission is prohibited")

    ci = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    for expected in ("--cov-fail-under=80", "--threshold 80 --fail", "--threshold 90 --fail"):
        if expected not in ci:
            failures.append(f"coverage enforcement weakened or removed: {expected}")

    scan = Path(".github/workflows/security-scan.yml").read_text(encoding="utf-8")
    if "--require-hashes -r requirements-security.lock" not in scan:
        failures.append("security scanner install must use the hash-locked requirements")
    if "bandit -r src -ll" not in scan:
        failures.append("Bandit medium/high severity gate missing")

    openssf = Path(".github/workflows/openssf-policy.yml").read_text(encoding="utf-8")
    for expected in (
        "scripts/check_pinned_actions.py",
        "scripts/manage_license_headers.py --check",
    ):
        if expected not in openssf:
            failures.append(f"OpenSSF policy enforcement missing: {expected}")

    readme = Path("README.md").read_text(encoding="utf-8")
    for pattern in PROHIBITED_README_CLAIMS:
        if re.search(pattern, readme, flags=re.IGNORECASE):
            failures.append(f"README contains a prohibited unevidenced trust claim: {pattern}")

    caiq_seed = Path("scripts/caiq_answers.py").read_text(encoding="utf-8")
    if "Historical seed answers" not in caiq_seed or "not the authoritative" not in caiq_seed:
        failures.append("legacy CAIQ seed must remain explicitly non-authoritative")

    if failures:
        print("Trust regression checks failed:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("Non-SLSA trust regression checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
