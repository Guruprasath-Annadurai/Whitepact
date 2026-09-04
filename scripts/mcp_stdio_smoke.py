#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Discover and safely call a local WhitePact MCP stdio server."""

from __future__ import annotations

import argparse
import asyncio
import json

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client


async def run(command: str) -> None:
    parameters = StdioServerParameters(command=command, args=[])
    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            resources = await session.list_resources()
            health = await session.call_tool("rai_health", {})

    print(f"tools={len(tools.tools)}")
    print(f"resources={len(resources.resources)}")
    print(f"rai_health_error={health.isError is True}")
    if health.structuredContent is not None:
        print(json.dumps(health.structuredContent, sort_keys=True))
    elif health.content and isinstance(health.content[0], types.TextContent):
        print(health.content[0].text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", default="whitepact-mcp")
    args = parser.parse_args()
    asyncio.run(run(args.command))


if __name__ == "__main__":
    main()
