"""``UpstreamMCPExecutor`` — the ``Executor`` (``governance/execution.py``)
that proxies one governed tool call to a registered external MCP
server, via the real MCP Python SDK client (the same one this project's
own tests already use to drive the hosted server: ``mcp.ClientSession`` +
``mcp.client.streamable_http.streamable_http_client``). Same structural
binding as ``InternalToolExecutor`` (``_validate_authorization()``,
imported not reimplemented) — an upstream call is exactly as bound to a
matching, unexpired, single-use, org-scoped ``ExecutionAuthorization``
as an internal one.

``action.target`` encodes both which server and which remote tool via
``build_upstream_target()``/``parse_upstream_target()`` — ``ActionRequest``
has no separate field for "which specific upstream endpoint," and adding
one would touch every other module that constructs an ``ActionRequest``
for no benefit outside this one executor.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import httpx

from responsibleai.governance.execution import ExecutionAuthorization, _validate_authorization
from responsibleai.governance.models import ActionRequest
from responsibleai.governance.risk import UPSTREAM_ACTION_TYPE
from responsibleai.governance.upstream import validate_upstream_server_url

ACTION_TYPE = UPSTREAM_ACTION_TYPE

if TYPE_CHECKING:
    from responsibleai.db.upstream_repository import UpstreamServerRepository

TARGET_SEPARATOR = "::"

# A proxied call to a third-party server must not hang the caller
# indefinitely, and must never follow a redirect -- a redirect could
# retarget the connection to a private address after the SSRF check
# already passed for the original URL (the same reasoning
# webhooks/manager.py's delivery path follows, though that module
# controls redirects via its own httpx call directly; here the guard is
# enforced by disabling redirect-following on the client altogether).
UPSTREAM_CALL_TIMEOUT_SECONDS = 30.0


class UpstreamServerNotAvailableError(Exception):
    """The named server isn't registered for this org, belongs to a
    different org, or is disabled -- covers all three uniformly (the
    caller doesn't need to distinguish "doesn't exist" from "exists but
    isn't yours," same 404-shaped reasoning the REST layer already
    applies to approvals)."""

    def __init__(self, server_id: str) -> None:
        self.server_id = server_id
        super().__init__(
            f"Upstream MCP server {server_id!r} is not available for this organization."
        )


class MalformedUpstreamTargetError(ValueError):
    def __init__(self, target: str) -> None:
        self.target = target
        super().__init__(
            f"Malformed upstream target {target!r}; expected 'server_id{TARGET_SEPARATOR}tool_name'."
        )


def build_upstream_target(server_id: str, tool_name: str) -> str:
    return f"{server_id}{TARGET_SEPARATOR}{tool_name}"


def parse_upstream_target(target: str) -> tuple[str, str]:
    server_id, sep, tool_name = target.partition(TARGET_SEPARATOR)
    if not sep or not server_id or not tool_name:
        raise MalformedUpstreamTargetError(target)
    return server_id, tool_name


class _HTTPClientFactory(Protocol):
    def __call__(self) -> httpx.AsyncClient: ...


def _default_http_client_factory() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=UPSTREAM_CALL_TIMEOUT_SECONDS, follow_redirects=False)


async def _call_upstream_tool(
    url: str,
    tool_name: str,
    arguments: dict[str, Any],
    *,
    http_client_factory: _HTTPClientFactory,
    auth_token: str | None,
) -> dict[str, Any]:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    async with http_client_factory() as http_client:
        if auth_token:
            http_client.headers["Authorization"] = f"Bearer {auth_token}"
        async with streamable_http_client(url, http_client=http_client) as (
            read_stream,
            write_stream,
            _get_session_id,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)

    return {
        "is_error": bool(result.isError),
        "content": [getattr(block, "text", str(block)) for block in result.content],
    }


class UpstreamMCPExecutor:
    """One instance per hosted-MCP process (or per test) — ``registry``
    is org-scoped lookup for "is this server_id real, mine, and
    enabled"; ``http_client_factory`` is a testability seam (the real
    default builds a genuine outbound ``httpx.AsyncClient``; tests
    inject one wired to an in-process ASGI transport instead of a real
    socket)."""

    def __init__(
        self,
        registry: UpstreamServerRepository,
        *,
        http_client_factory: _HTTPClientFactory | None = None,
    ) -> None:
        self._registry = registry
        # Resolved at call time (execute()), not bound here as a default
        # parameter value -- a default value captures a reference to
        # whatever _default_http_client_factory *was* at class-
        # definition/import time, so monkeypatching the module-level
        # name later (the standard test seam for "swap this for a
        # fake") would silently have no effect. None here just means
        # "use whatever the module-level name currently points to."
        self._http_client_factory = http_client_factory

    async def execute(self, authorization: ExecutionAuthorization, action: ActionRequest) -> Any:
        _validate_authorization(authorization, action)
        authorization.consumed = True  # single-use, same as InternalToolExecutor

        server_id, tool_name = parse_upstream_target(action.target)
        server = await self._registry.get(server_id)
        if server is None or server.org_id != action.agent.organization_id or not server.enabled:
            raise UpstreamServerNotAvailableError(server_id)

        # Re-checked immediately before dispatch, not just at
        # registration -- DNS can resolve differently between the two
        # (validate_upstream_server_url's own docstring).
        validate_upstream_server_url(server.url)

        factory = self._http_client_factory or _default_http_client_factory
        return await _call_upstream_tool(
            server.url,
            tool_name,
            action.arguments,
            http_client_factory=factory,
            auth_token=server.auth_token,
        )
