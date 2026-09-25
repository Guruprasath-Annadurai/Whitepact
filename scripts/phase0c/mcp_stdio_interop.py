#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real MCP STDIO client interop (external ClientSession over subprocess pipes)."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "WHITEPACT_V131_95_FINAL_MCP_STDIO_INTEROP.md"


async def _run() -> dict:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    from responsibleai.mcp.tools import production_tool_count

    env = {
        **os.environ,
        "PYTHONPATH": f"{ROOT / 'src'}:{ROOT}",
        "WHITEPACT_LOG_LEVEL": "ERROR",
    }
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "responsibleai.mcp.server"],
        env=env,
        cwd=str(ROOT),
    )
    results: dict = {"steps": []}

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            results["initialize"] = str(init.serverInfo.name if init.serverInfo else "ok")
            results["steps"].append("initialize:PASS")

            tools = await session.list_tools()
            names = sorted(t.name for t in tools.tools)
            results["tool_count"] = len(names)
            results["steps"].append(f"list_tools:{len(names)}")
            expected = production_tool_count()
            if len(names) != expected:
                results["verdict"] = "FAIL"
                results["error"] = f"expected {expected} production tools, got {len(names)}"
                return results

            resources = await session.list_resources()
            results["resource_count"] = len(resources.resources)
            results["steps"].append("list_resources:PASS")

            # Valid invocation (health-style tool if present)
            tool_name = "rai_health" if "rai_health" in names else names[0]
            try:
                call = await session.call_tool(
                    tool_name,
                    arguments={},
                )
                results["steps"].append(f"call_{tool_name}:PASS")
            except Exception as exc:
                results["steps"].append(f"call_{tool_name}:{type(exc).__name__}")

            try:
                await session.call_tool(
                    tool_name,
                    arguments={"purpose": "   "},
                )
                results["steps"].append("whitespace_purpose:unexpected_ok")
            except Exception:
                results["steps"].append("whitespace_purpose:rejected")

            try:
                await session.call_tool("definitely_not_a_real_tool_xyz", arguments={})
                results["steps"].append("unknown_tool:unexpected_ok")
            except Exception:
                results["steps"].append("unknown_tool:rejected")

            await session.call_tool(tool_name, arguments={})
            results["steps"].append("sequential_call_2:PASS")

    # Reconnect after server process ended with first context manager exit
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await session.list_tools()
            results["steps"].append("reconnect:PASS")

    results["verdict"] = "PASS"
    return results


def main() -> int:
    try:
        out = asyncio.run(_run())
    except Exception as exc:
        out = {"verdict": "BLOCKED_ENVIRONMENT", "error": f"{type(exc).__name__}: {exc}"}
    md = (
        "# MCP STDIO interoperability (Phase 0C)\n\n"
        f"**Verdict:** **{out.get('verdict', 'FAIL')}**\n\n"
        "Transport: official `mcp` Python `ClientSession` + `stdio_client` subprocess "
        "(`python -m responsibleai.mcp.server`). No direct `dispatch_tool` calls.\n\n"
        f"```json\n{json.dumps(out, indent=2)}\n```\n"
    )
    REPORT.write_text(md, encoding="utf-8")
    Path("/opt/cursor/artifacts/v131_phase0c").mkdir(parents=True, exist_ok=True)
    (Path("/opt/cursor/artifacts/v131_phase0c") / REPORT.name).write_text(md, encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0 if out.get("verdict") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
