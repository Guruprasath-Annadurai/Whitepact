#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Fail when current public MCP counts drift from the live definitions."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from responsibleai.mcp.resources import (  # noqa: E402
    _CANONICAL_RESOURCE_DEFS,
    RESOURCE_DEFS,
)
from responsibleai.mcp.tools import TOOL_DEFS  # noqa: E402

CURRENT_DOCS = (
    "README.md",
    "CONTRIBUTING.md",
    "docs/mcp/README.md",
    "docs/integrations/README.md",
    "docs/integrations/PLATFORM_COMPATIBILITY.md",
    "docs/integrations/claude.md",
    "docs/integrations/cursor.md",
    "docs/integrations/github-copilot.md",
    "docs/integrations/gemini.md",
    "docs/integrations/grok.md",
    "docs/integrations/aws-agentcore.md",
    "docs/integrations/kiro-cli.md",
    "docs/integrations/FOUNDER_ACTIONS.md",
    "compliance/MCP_DISTRIBUTION_GUIDE.md",
    "compliance/CONNECTOR_READINESS_REPORT.md",
    "compliance/OEM_LICENSING.md",
)


def main() -> int:
    expected_tools = len(TOOL_DEFS)
    expected_resources = len(RESOURCE_DEFS)
    expected_canonical = len(_CANONICAL_RESOURCE_DEFS)
    failures: list[str] = []

    manifest = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
    meta = manifest["_meta"]["io.modelcontextprotocol.registry/publisher-provided"]
    actual_manifest = (
        meta["tool_count"],
        meta["resource_count_advertised"],
        meta["resource_count_canonical"],
    )
    expected_manifest = (expected_tools, expected_resources, expected_canonical)
    if actual_manifest != expected_manifest:
        failures.append(
            f"server.json counts {actual_manifest} do not match live definitions "
            f"{expected_manifest}"
        )

    for relative in CURRENT_DOCS:
        text = (ROOT / relative).read_text(encoding="utf-8")
        if "27 tools" in text or "27-tool" in text:
            failures.append(f"{relative} still presents the superseded 27-tool count")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if f"Available tools ({expected_tools})" not in readme:
        failures.append("README tool-table heading does not match live definitions")
    for tool in TOOL_DEFS:
        if f"`{tool.name}`" not in readme:
            failures.append(f"README tool table omits {tool.name}")

    if failures:
        print("MCP documentation consistency check FAILED:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(
        "MCP documentation consistency OK "
        f"({expected_tools} tools, {expected_resources} advertised / "
        f"{expected_canonical} canonical resources)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
