"""Tool discovery/aggregation for the MCP Upstream Gateway (v3
authority-layer work, Task #144's bounded scope).

Honest scoping, stated plainly: this lists what tools each of an org's
registered upstream servers currently advertises, namespaced
(``server_id::tool_name``, matching ``upstream_executor.py``'s own
``build_upstream_target()`` convention) so a caller/dashboard can
discover what's callable before actually calling
``UpstreamMCPExecutor``. It does **not** inject these into the live MCP
protocol's own ``tools/list`` response (``mcp/server.py``'s tool
listing stays exactly what it was — this platform's own static 27
tools) — that would mean restructuring a currently static, org-agnostic
tool list into a per-request, per-org dynamic one, a materially larger
and riskier change (caching, plan-gating, and every existing tool-list
test would need to change) than "let a caller ask what's out there."
Building that is real, separate, deferred work, not implied by this
module.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from responsibleai.governance.upstream import (
    UnsafeUpstreamServerURLError,
    validate_upstream_server_url,
)
from responsibleai.governance.upstream_executor import (
    _default_http_client_factory,
    build_upstream_target,
)

if TYPE_CHECKING:
    from responsibleai.db.upstream_repository import UpstreamServerRepository
    from responsibleai.governance.upstream import UpstreamServer
    from responsibleai.governance.upstream_executor import _HTTPClientFactory

_logger = logging.getLogger("responsibleai.governance.upstream_discovery")

# A down/slow upstream server must not hang tool discovery for the rest
# of an org's registered servers -- each server's list_tools() call is
# individually bounded, and a timeout on one is reported as its own
# error entry, not raised out of the whole aggregation.
DISCOVERY_TIMEOUT_SECONDS = 10.0


@dataclass
class UpstreamToolDescriptor:
    server_id: str
    server_name: str
    tool_name: str
    namespaced_name: str
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "server_id": self.server_id,
            "server_name": self.server_name,
            "tool_name": self.tool_name,
            "namespaced_name": self.namespaced_name,
            "description": self.description,
        }


async def _list_tools_for_server(
    server: UpstreamServer, *, http_client_factory: _HTTPClientFactory,
) -> list[UpstreamToolDescriptor]:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    async with http_client_factory() as http_client:
        if server.auth_token:
            http_client.headers["Authorization"] = f"Bearer {server.auth_token}"
        async with streamable_http_client(server.url, http_client=http_client) as (
            read_stream, write_stream, _get_session_id,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.list_tools()

    return [
        UpstreamToolDescriptor(
            server_id=server.server_id,
            server_name=server.name,
            tool_name=tool.name,
            namespaced_name=build_upstream_target(server.server_id, tool.name),
            description=tool.description or "",
        )
        for tool in result.tools
    ]


async def discover_upstream_tools(
    registry: UpstreamServerRepository,
    org_id: str,
    *,
    http_client_factory: _HTTPClientFactory | None = None,
) -> tuple[list[UpstreamToolDescriptor], dict[str, str]]:
    """Queries every enabled server registered to *org_id* for its
    current tool list, in parallel. Returns ``(tools, errors)`` --
    *errors* maps ``server_id -> error message`` for any server that
    couldn't be reached or rejected the SSRF re-check, so one broken
    registration doesn't silently hide every other server's tools (or
    make the whole endpoint fail)."""
    factory = http_client_factory or _default_http_client_factory
    servers = [s for s in await registry.list_for_org(org_id) if s.enabled]

    async def _one(server: UpstreamServer) -> tuple[str, list[UpstreamToolDescriptor] | None, str | None]:
        try:
            validate_upstream_server_url(server.url)
            tools = await asyncio.wait_for(
                _list_tools_for_server(server, http_client_factory=factory),
                timeout=DISCOVERY_TIMEOUT_SECONDS,
            )
            return server.server_id, tools, None
        except UnsafeUpstreamServerURLError as exc:
            return server.server_id, None, str(exc)
        except TimeoutError:
            return server.server_id, None, f"timed out after {DISCOVERY_TIMEOUT_SECONDS}s"
        except Exception as exc:  # noqa: BLE001 -- one server's failure must not sink discovery for the rest
            _logger.warning("upstream_tool_discovery_failed server_id=%s error=%s", server.server_id, exc)
            return server.server_id, None, str(exc)

    results = await asyncio.gather(*(_one(s) for s in servers))

    all_tools: list[UpstreamToolDescriptor] = []
    errors: dict[str, str] = {}
    for server_id, tools, error in results:
        if error is not None:
            errors[server_id] = error
        elif tools is not None:
            all_tools.extend(tools)
    return all_tools, errors
