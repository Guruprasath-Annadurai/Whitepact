#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Check local Markdown links on the public launch surface."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DOCS = (
    "README.md",
    "PROMOTION_READINESS.md",
    "SECURITY.md",
    "SUPPORT.md",
    "CONTRIBUTING.md",
    "docs/QUICKSTART.md",
    "docs/mcp/README.md",
    "docs/enterprise/README.md",
    "docs/promotion/LAUNCH_COPY.md",
)
LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def main() -> int:
    failures: list[str] = []
    for relative in PUBLIC_DOCS:
        source = ROOT / relative
        for raw_target in LINK.findall(source.read_text(encoding="utf-8")):
            target = raw_target.strip().strip("<>")
            if target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            path_part = unquote(target.split("#", 1)[0])
            if not path_part:
                continue
            resolved = (source.parent / path_part).resolve()
            if not resolved.exists():
                failures.append(f"{relative}: missing local target {target}")

    if failures:
        print("Launch-surface local link check FAILED:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print(f"Launch-surface local links OK ({len(PUBLIC_DOCS)} documents).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
