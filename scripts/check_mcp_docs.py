#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Fail when current public MCP counts drift from the live definitions."""

from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

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


def _literal_list(path: str, variable: str) -> ast.List:
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"), filename=path)
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == variable and isinstance(node.value, ast.List):
                return node.value
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == variable for target in node.targets
        ):
            if isinstance(node.value, ast.List):
                return node.value
    raise RuntimeError(f"{path}: {variable} is no longer a literal list")


def _tool_names() -> list[str]:
    definitions = _literal_list("src/responsibleai/mcp/tools.py", "TOOL_DEFS")
    names: list[str] = []
    for definition in definitions.elts:
        if not isinstance(definition, ast.Call):
            raise RuntimeError("TOOL_DEFS contains a non-call entry")
        name = next((item.value for item in definition.keywords if item.arg == "name"), None)
        if not isinstance(name, ast.Constant) or not isinstance(name.value, str):
            raise RuntimeError("TOOL_DEFS contains an entry without a literal name")
        names.append(name.value)
    return names


def main() -> int:
    tool_names = _tool_names()
    expected_tools = len(tool_names)
    expected_canonical = len(
        _literal_list("src/responsibleai/mcp/resources.py", "_CANONICAL_RESOURCE_DEFS").elts
    )
    expected_resources = 2 * expected_canonical
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
    for tool_name in tool_names:
        if f"`{tool_name}`" not in readme:
            failures.append(f"README tool table omits {tool_name}")

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
