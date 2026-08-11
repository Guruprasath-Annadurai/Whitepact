"""
WhitePact MCP Server (governance tools for Claude Code and MCP-compatible
AI assistants) — the governance engine behind WhitePact's runtime
authority layer. See MIGRATION_WHITEPACT_V2.md Section 6: the server's
protocol-level identity is `whitepact`; the console script names
(`responsibleai-mcp`/`responsibleai-mcp-http`) launching this exact
process are unchanged, kept for backward compatibility. MCP clients
treat the server name as an opaque display string, not a dependency, so
this rename carries no compatibility break.

Three transports:

1. **stdio** (default, free, self-hosted) — full unrestricted tool access.
   Configure Claude Code:
       {
         "mcpServers": {
           "whitepact": { "command": "responsibleai-mcp" }
         }
       }

2. **Streamable HTTP** (hosted, billed) — the modern MCP HTTP transport
   (spec 2025-03-26+): a single `/mcp` endpoint, Bearer-token authenticated,
   tools gated by the calling org's billing Plan (FREE/PRO/ENTERPRISE — see
   mcp/licensing.py). This is the **preferred** hosted transport — point new
   clients here. Run with: `responsibleai-mcp-http` (reads RAI_MCP_HTTP_*
   env vars).

3. **HTTP+SSE** (hosted, billed, legacy) — the original MCP HTTP transport
   (spec 2024-11-05): separate `/sse` + `/messages/` endpoints. Same auth and
   plan-gating as Streamable HTTP. Kept running, unmodified, for existing
   clients built against it — see MIGRATION_WHITEPACT_V2.md Section 7 for
   the deprecation posture (no removal date; migrate at your own pace).

Both hosted transports are served by the same `main_http()` process on the
same port; a client picks its transport by which path it connects to.

Environment variables (all optional):
    RAI_MCP_LOG_LEVEL     Logging level: DEBUG | INFO | WARNING (default: WARNING)
    RAI_MCP_HTTP_HOST     HTTP transport bind host (default: 0.0.0.0)
    RAI_MCP_HTTP_PORT     HTTP transport bind port (default: 8766)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from responsibleai.mcp.licensing import (
    is_allowed,
    monthly_quota,
    quota_exceeded_message,
    upgrade_message,
)
from responsibleai.mcp.resources import RESOURCE_DEFS, dispatch_resource
from responsibleai.mcp.tools import TOOL_DEFS, dispatch_tool
from responsibleai.rbac.models import OrgContext

if TYPE_CHECKING:
    from responsibleai.db.mcp_usage_repository import McpUsageRepository

_log_level = os.environ.get("RAI_MCP_LOG_LEVEL", "WARNING").upper()
logging.basicConfig(level=getattr(logging, _log_level, logging.WARNING))
_logger = logging.getLogger("responsibleai.mcp")

server: Server = Server("whitepact")

# Legacy console-script name -> its preferred replacement, per
# pyproject.toml's [project.scripts] (Migration Section 4). Both sides
# of each pair launch the identical entry-point function.
_LEGACY_TO_PREFERRED_NAME = {
    "responsibleai-mcp": "whitepact-mcp",
    "responsibleai-mcp-http": "whitepact-mcp-http",
}


def _invoked_as() -> str:
    """The console-script name this process was actually launched under
    (e.g. "whitepact-mcp" or the legacy "responsibleai-mcp") — read from
    argv[0], not hardcoded, so it reflects reality regardless of which
    of the aliases in pyproject.toml's [project.scripts] launched it."""
    return os.path.basename(sys.argv[0]) if sys.argv else "unknown"


def _log_invocation_name(process_kind: str) -> None:
    """MIGRATION_WHITEPACT_V2.md Section 4: log which entry-point name
    launched this process, for observability during the transition —
    stderr/structured logging only, never stdout, since stdout is the
    stdio MCP transport itself and writing to it would corrupt the
    protocol on every `main()` (stdio) invocation."""
    invoked_as = _invoked_as()
    preferred = _LEGACY_TO_PREFERRED_NAME.get(invoked_as)
    if preferred is not None:
        _logger.info(
            "%s started via the legacy '%s' command — the preferred name is "
            "'%s'. Both keep working; see MIGRATION_WHITEPACT_V2.md.",
            process_kind, invoked_as, preferred,
        )
    else:
        _logger.info("%s started via '%s'.", process_kind, invoked_as)

# Set by the HTTP transport's auth middleware per-connection. None on stdio
# (self-hosted) — absence of a context means unrestricted access, matching
# the open-core design: self-hosted stdio is always free and full-featured.
_current_org: ContextVar[OrgContext | None] = ContextVar("_current_org", default=None)
_current_usage_repo: ContextVar[McpUsageRepository | None] = ContextVar(
    "_current_usage_repo", default=None
)


def _month_start_iso() -> str:
    now = datetime.now(UTC)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


@server.list_tools()
async def _list_tools() -> list[types.Tool]:
    return TOOL_DEFS


@server.call_tool()
async def _call_tool(
    name: str,
    arguments: dict[str, Any] | None,
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    _logger.debug("tool_call name=%s args=%s", name, arguments)

    ctx = _current_org.get()
    usage_repo = _current_usage_repo.get()

    if ctx is not None:
        if not is_allowed(name, ctx.plan):
            if usage_repo is not None and ctx.org_id:
                await usage_repo.record_call(ctx.org_id, name, ctx.plan.value, allowed=False)
            error = {"error": "upgrade_required", "message": upgrade_message(name, ctx.plan)}
            return [types.TextContent(type="text", text=json.dumps(error, indent=2))]

        quota = monthly_quota(ctx.plan)
        if quota == 0:
            if usage_repo is not None and ctx.org_id:
                await usage_repo.record_call(ctx.org_id, name, ctx.plan.value, allowed=False)
            error = {
                "error": "hosted_access_unavailable",
                "message": (
                    f"The {ctx.plan.value} plan does not include hosted MCP access. "
                    "Use the free self-hosted stdio transport, or upgrade at "
                    "https://responsibleai.dev/pricing."
                ),
            }
            return [types.TextContent(type="text", text=json.dumps(error, indent=2))]

        if quota is not None and usage_repo is not None and ctx.org_id:
            used = await usage_repo.count_since(ctx.org_id, _month_start_iso())
            if used >= quota:
                await usage_repo.record_call(ctx.org_id, name, ctx.plan.value, allowed=False)
                error = {
                    "error": "quota_exceeded",
                    "message": quota_exceeded_message(ctx.plan, used, quota),
                }
                return [types.TextContent(type="text", text=json.dumps(error, indent=2))]

        if usage_repo is not None and ctx.org_id:
            await usage_repo.record_call(ctx.org_id, name, ctx.plan.value, allowed=True)

    result = await dispatch_tool(name, arguments or {})
    return [types.TextContent(type="text", text=json.dumps(result, indent=2, default=str))]


@server.list_resources()
async def _list_resources() -> list[types.Resource]:
    return RESOURCE_DEFS


@server.read_resource()
async def _read_resource(uri: types.AnyUrl) -> str:
    _logger.debug("resource_read uri=%s", uri)
    return await dispatch_resource(str(uri))


# ── stdio transport (self-hosted, free, unrestricted) ──────────────────────────

async def _run_stdio() -> None:
    async with stdio_server() as (read_stream, write_stream):
        init_options = server.create_initialization_options()
        await server.run(read_stream, write_stream, init_options)


def main() -> None:
    """CLI entry point: whitepact-mcp / responsibleai-mcp (stdio, self-hosted)."""
    _logger.info("starting %s v1.2.0 (stdio)", server.name)
    _log_invocation_name("stdio server")
    asyncio.run(_run_stdio())


# ── HTTP/SSE transport (hosted, billed, plan-gated) ─────────────────────────────

def _build_http_app() -> Any:
    """Construct the ASGI app for hosted MCP. Imports are local — this path
    pulls in Starlette + the DB layer, which self-hosted stdio users never need.

    Serves both hosted transports on one app — see the module docstring:
    `/mcp` (Streamable HTTP, preferred) and `/sse` + `/messages/` (legacy
    HTTP+SSE, unmodified). Both share the same auth (`_authenticate`) and
    the same plan-gating contextvars consumed by `_call_tool`.
    """
    from contextlib import asynccontextmanager

    from mcp.server.sse import SseServerTransport
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.routing import Mount, Route
    from starlette.types import Receive, Scope, Send

    from responsibleai.dashboard.config import get_settings
    from responsibleai.db import McpUsageRepository, OrgRepository, create_engine

    settings = get_settings()
    _db_engine = create_engine(settings.effective_db_url)
    _org_repo = OrgRepository(_db_engine)
    _usage_repo = McpUsageRepository(_db_engine)
    sse = SseServerTransport("/messages/")
    # stateless=True: each POST to /mcp is authenticated and dispatched
    # independently, mirroring the legacy /sse transport's per-connection
    # Bearer auth rather than introducing cross-request session affinity.
    streamable_http = StreamableHTTPSessionManager(app=server, stateless=True)

    @asynccontextmanager
    async def _lifespan(_app: Starlette) -> Any:
        await _db_engine.init()
        async with streamable_http.run():
            yield

    async def _authenticate(request: Request) -> OrgContext | None:
        auth_header = request.headers.get("authorization", "")
        if not auth_header.lower().startswith("bearer "):
            return None
        raw_key = auth_header[7:].strip()
        if not raw_key:
            return None
        return await _org_repo.authenticate(raw_key)

    async def handle_sse(request: Request) -> Any:
        ctx = await _authenticate(request)
        if ctx is None:
            return JSONResponse(
                {"error": "unauthorized", "message": "Provide a valid Bearer API key."},
                status_code=401,
            )

        org_token = _current_org.set(ctx)
        usage_token = _current_usage_repo.set(_usage_repo)
        try:
            async with sse.connect_sse(
                request.scope, request.receive, request._send
            ) as (read_stream, write_stream):
                init_options = server.create_initialization_options()
                await server.run(read_stream, write_stream, init_options)
        finally:
            _current_org.reset(org_token)
            _current_usage_repo.reset(usage_token)
        return JSONResponse({}, status_code=200)

    class _StreamableHttpEndpoint:
        """A plain `async def` here would make Starlette's `Route` treat it
        as a `func(request) -> Response` handler (see `Route.__init__`'s
        `inspect.isfunction` check) and wrap it in `request_response`,
        which is incompatible with `StreamableHTTPSessionManager.handle_request`'s
        raw `(scope, receive, send)` ASGI signature. A callable *instance*
        fails that isfunction/ismethod check, so Route mounts it as ASGI
        directly — and unlike `Mount`, `Route` matches the exact path with
        no wildcard remainder, so `/mcp` needs no trailing slash and never
        307-redirects the way `Mount("/mcp", ...)` would.
        """

        async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
            request = Request(scope, receive=receive)
            ctx = await _authenticate(request)
            if ctx is None:
                response = JSONResponse(
                    {"error": "unauthorized", "message": "Provide a valid Bearer API key."},
                    status_code=401,
                )
                await response(scope, receive, send)
                return

            org_token = _current_org.set(ctx)
            usage_token = _current_usage_repo.set(_usage_repo)
            try:
                await streamable_http.handle_request(scope, receive, send)
            finally:
                _current_org.reset(org_token)
                _current_usage_repo.reset(usage_token)

    handle_streamable_http = _StreamableHttpEndpoint()

    async def health(request: Request) -> JSONResponse:
        return JSONResponse({
            "status": "ok",
            # "transport" (singular) is kept for existing consumers of this
            # diagnostics endpoint; "transports" is the new, complete list.
            "transport": "http+sse",
            "transports": ["streamable-http", "http+sse"],
            "tools": len(TOOL_DEFS),
        })

    app = Starlette(
        routes=[
            Route("/health", endpoint=health),
            Route("/mcp", endpoint=handle_streamable_http),
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
        lifespan=_lifespan,
    )

    return app


def main_http() -> None:
    """CLI entry point: whitepact-mcp-http / responsibleai-mcp-http (hosted, Bearer-authenticated, plan-gated)."""
    import uvicorn

    host = os.environ.get("RAI_MCP_HTTP_HOST", "0.0.0.0")
    port = int(os.environ.get("RAI_MCP_HTTP_PORT", "8766"))
    _logger.info("starting %s v1.2.0 (http+sse) on %s:%s", server.name, host, port)
    _log_invocation_name("http+sse server")
    uvicorn.run(_build_http_app(), host=host, port=port)


if __name__ == "__main__":
    main()
