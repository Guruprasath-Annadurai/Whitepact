#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Fail CI if a GitHub Actions dependency is not pinned to a full commit SHA.

OpenSSF Scorecard's Pinned-Dependencies check treats movable tags such as
``actions/checkout@v4`` as weaker than immutable commit references. This
checker prevents future workflow edits from silently reintroducing movable
action refs after the repository has been hardened.
"""

from __future__ import annotations

import re
from pathlib import Path

WORKFLOWS = Path(".github/workflows")
USES_RE = re.compile(r"^\s*uses:\s*([^#\s]+)")
SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")


def main() -> int:
    failures: list[str] = []

    for path in sorted(WORKFLOWS.glob("*.y*ml")):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            match = USES_RE.match(line)
            if not match:
                continue

            value = match.group(1).strip("'\"")
            if value.startswith("./"):
                # Local actions are supplied by this same reviewed checkout.
                continue

            action, separator, ref = value.rpartition("@")
            if not separator or not action or not SHA_RE.fullmatch(ref):
                failures.append(f"{path}:{line_number}: {value}")

    if failures:
        print("GitHub Actions dependencies must use immutable 40-character commit SHAs:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("All GitHub Actions dependencies are pinned to immutable commit SHAs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
