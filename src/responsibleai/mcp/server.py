"""
ResponsibleAI MCP Server — governance tools for Claude Code and MCP-compatible AI assistants.

Two transports:

1. **stdio** (default, free, self-hosted) — full unrestricted tool access.
   Configure Claude Code:
       {
         "mcpServers": {
           "responsibleai": { "command": "responsibleai-mcp" }
         }
       }

2. **HTTP/SSE** (hosted, billed) — Bearer-token authenticated, tools gated by
   the calling org's billing Plan (FREE/PRO/ENTERPRISE — see mcp/licensing.py).
   Run with: `responsibleai-mcp-http` (reads RAI_MCP_HTTP_* env vars).

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
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from responsibleai.mcp.licensing import is_allowed, monthly_quota, quota_exceeded_message, upgrade_message
from responsibleai.mcp.resources import RESOURCE_DEFS, dispatch_resource
from responsibleai.mcp.tools import TOOL_DEFS, dispatch_tool
from responsibleai.rbac.models import OrgContext, Plan

if TYPE_CHECKING:
    from responsibleai.db.mcp_usage_repository import McpUsageRepository

_log_level = os.environ.get("RAI_MCP_LOG_LEVEL", "WARNING").upper()
logging.basicConfig(level=getattr(logging, _log_level, logging.WARNING))
_logger = logging.getLogger("responsibleai.mcp")

server: Server = Server("responsibleai-mcp")

# Set by the HTTP transport's auth middleware per-connection. None on stdio
# (self-hosted) — absence of a context means unrestricted access, matching
# the open-core design: self-hosted stdio is always free and full-featured.
_current_org: ContextVar[OrgContext | None] = ContextVar("_current_org", default=None)
_current_usage_repo: ContextVar["McpUsageRepository | None"] = ContextVar(
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
    """CLI entry point: responsibleai-mcp (stdio, self-hosted)."""
    _logger.info("starting responsibleai-mcp v1.2.0 (stdio)")
    asyncio.run(_run_stdio())


# ── HTTP/SSE transport (hosted, billed, plan-gated) ─────────────────────────────

def _build_http_app() -> Any:
    """Construct the ASGI app for hosted MCP. Imports are local — this path
    pulls in Starlette + the DB layer, which self-hosted stdio users never need.
    """
    from starlette.applications import Starlette
    from starlette.requests import Request
    from contextlib import asynccontextmanager

    from starlette.responses import JSONResponse
    from starlette.routing import Mount, Route

    from mcp.server.sse import SseServerTransport

    from responsibleai.dashboard.config import get_settings
    from responsibleai.db import McpUsageRepository, OrgRepository, create_engine

    settings = get_settings()
    _db_engine = create_engine(settings.effective_db_url)
    _org_repo = OrgRepository(_db_engine)
    _usage_repo = McpUsageRepository(_db_engine)
    sse = SseServerTransport("/messages/")

    @asynccontextmanager
    async def _lifespan(_app: Starlette) -> Any:
        await _db_engine.init()
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

    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "transport": "http+sse", "tools": len(TOOL_DEFS)})

    app = Starlette(
        routes=[
            Route("/health", endpoint=health),
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
        lifespan=_lifespan,
    )

    return app


def main_http() -> None:
    """CLI entry point: responsibleai-mcp-http (hosted, Bearer-authenticated, plan-gated)."""
    import uvicorn

    host = os.environ.get("RAI_MCP_HTTP_HOST", "0.0.0.0")
    port = int(os.environ.get("RAI_MCP_HTTP_PORT", "8766"))
    _logger.info("starting responsibleai-mcp v1.2.0 (http+sse) on %s:%s", host, port)
    uvicorn.run(_build_http_app(), host=host, port=port)


if __name__ == "__main__":
    main()
