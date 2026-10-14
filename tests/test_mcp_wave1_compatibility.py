# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real-process stdio and real-TCP hosted compatibility; not production qualification.

Hosted authority is explicitly seeded by the existing local fixture. Community
stdio is intentionally ungoverned and is never represented as enterprise access.
"""

from __future__ import annotations

import asyncio
import json
import socket
import sys
from pathlib import Path
from unittest import mock

import httpx
import pytest
import uvicorn
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client

from tests import test_mcp_governance_dispatch as _governance

governed_app_with_key = _governance.governed_app_with_key

ROOT = Path(__file__).resolve().parents[1]


def _stdio_env(domain: str) -> dict[str, str]:
    # Do not inherit host credentials or local runtime .env files.
    return {
        "PYTHONPATH": str(ROOT / "src"),
        "WHITEPACT_ENV": "development",
        "WHITEPACT_MCP_TRUST_DOMAIN": domain,
    }


async def test_real_stdio_discovery_ping_and_unknown_tool(tmp_path) -> None:
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "responsibleai.mcp.server"],
        env=_stdio_env("community"),
        cwd=str(tmp_path),
    )
    with (tmp_path / "stdio.stderr").open("w+") as stderr:
        async with asyncio.timeout(30), stdio_client(parameters, errlog=stderr) as streams:
            async with ClientSession(*streams) as session:
                initialized = await session.initialize()
                assert initialized.serverInfo.name
                assert initialized.capabilities.tools is not None
                await session.send_ping()
                tools = await session.list_tools()
                assert "rai_health" in {tool.name for tool in tools.tools}
                assert "test.counter.increment" not in {tool.name for tool in tools.tools}
                resources = await session.list_resources()
                assert resources.resources
                unknown = await session.call_tool("not.a.real.tool", {})
                assert unknown.isError or any(
                    "error" in json.loads(item.text)
                    for item in unknown.content
                    if item.type == "text"
                )
        stderr.seek(0)
        assert "UNGOVERNED LOCAL MODE" in stderr.read()


async def test_real_enterprise_stdio_process_refuses_before_protocol(tmp_path) -> None:
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "responsibleai.mcp.server",
        cwd=tmp_path,
        env=_stdio_env("enterprise"),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
        assert process.returncode == 2
        assert stdout == b""
        assert b"forbids ungoverned stdio" in stderr
        assert b"UNGOVERNED LOCAL MODE" not in stderr
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


@pytest.fixture()
async def tcp_mcp(governed_app_with_key):
    app, raw, org, engine, key_id = governed_app_with_key
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    port = listener.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(app, lifespan="off", log_level="error", access_log=False)
    )
    task = asyncio.create_task(server.serve(sockets=[listener]))
    try:
        async with asyncio.timeout(10):
            while not server.started:
                if task.done():
                    task.result()
                    raise AssertionError("MCP TCP server stopped before startup")
                await asyncio.sleep(0.01)
        yield f"http://127.0.0.1:{port}", raw, org, engine, key_id
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, timeout=10)
        listener.close()


async def test_real_tcp_client_discovery_ping_unknown_resource_and_tool(tcp_mcp) -> None:
    origin, raw, *_ = tcp_mcp
    async with (
        httpx.AsyncClient(headers={"Authorization": f"Bearer {raw}"}) as client,
        streamable_http_client(f"{origin}/mcp", http_client=client) as streams,
        ClientSession(streams[0], streams[1]) as session,
    ):
        await session.initialize()
        await session.send_ping()
        tools = await session.list_tools()
        names = [tool.name for tool in tools.tools]
        assert "rai_health" in names
        assert "test.counter.increment" not in names
        assert len(names) == len(set(names))
        assert (await session.list_resources()).resources
        missing = await session.read_resource("whitepact://does-not-exist")
        assert missing.contents
        assert "error" in json.loads(missing.contents[0].text)
        missing_purpose = await session.call_tool("rai_health", {})
        assert missing_purpose.structuredContent["error"] == "governance_purpose_required"
        unknown = await session.call_tool(
            "not.a.real.tool", {"whitepact_purpose": "automated-test"}
        )
        assert unknown.isError or "error" in (unknown.structuredContent or {})


async def test_real_tcp_malformed_and_invalid_arguments_never_dispatch(tcp_mcp) -> None:
    origin, raw, *_ = tcp_mcp
    headers = {
        "Authorization": f"Bearer {raw}",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    with mock.patch("responsibleai.mcp.server.dispatch_tool", new=mock.AsyncMock()) as dispatch:
        async with httpx.AsyncClient(base_url=origin, headers=headers) as client:
            malformed = await client.post("/mcp", content=b"{invalid-json")
            assert 400 <= malformed.status_code < 500
            invalid = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "rai_scan", "arguments": {"text": 123}},
                },
            )
            assert invalid.status_code == 200
            payload = next(
                json.loads(line[5:].strip())
                for line in invalid.text.splitlines()
                if line.startswith("data:")
            )
            assert payload.get("error") or payload["result"].get("isError") is True
        dispatch.assert_not_awaited()


async def test_real_tcp_revoked_key_cannot_reuse_discovery_session(tcp_mcp) -> None:
    from responsibleai.db import OrgRepository

    origin, raw, org, engine, key_id = tcp_mcp
    headers = {
        "Authorization": f"Bearer {raw}",
        "Accept": "application/json, text/event-stream",
    }
    async with httpx.AsyncClient(base_url=origin, headers=headers) as client:
        first = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        assert first.status_code == 200
        assert await OrgRepository(engine).revoke_key(key_id, org)
        refused = await client.post(
            "/mcp",
            headers={"Mcp-Session-Id": first.headers.get("mcp-session-id", "forged")},
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        )
        assert refused.status_code == 401
        assert raw not in refused.text
        legacy = await client.get("/sse")
        assert legacy.status_code == 401
        assert raw not in legacy.text
