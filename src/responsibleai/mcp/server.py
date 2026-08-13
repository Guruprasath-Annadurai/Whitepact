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

   The Bearer credential is either a static API key (`rai_...`, issued via
   `OrgRepository.create_key`) or, when this deployment has SSO configured
   (`Settings.oidc_issuer` — the exact same config the dashboard API's
   `/api/auth/login/oidc` already uses), an OIDC-issued JWT. This makes the
   hosted MCP server an OAuth/OIDC *resource server*: it validates tokens
   issued by the org's existing Authorization Server rather than running
   its own. When OIDC is configured, `/.well-known/oauth-protected-resource`
   (RFC 9728) advertises it, and a `401` includes a `WWW-Authenticate:
   Bearer resource_metadata="..."` header pointing there.

3. **HTTP+SSE** (hosted, billed, legacy) — the original MCP HTTP transport
   (spec 2024-11-05): separate `/sse` + `/messages/` endpoints. Same auth and
   plan-gating as Streamable HTTP. Kept running, unmodified, for existing
   clients built against it — see MIGRATION_WHITEPACT_V2.md Section 7 for
   the deprecation posture (no removal date; migrate at your own pace).

Both hosted transports are served by the same `main_http()` process on the
same port; a client picks its transport by which path it connects to.

Environment variables (all optional):
    RAI_MCP_LOG_LEVEL                     Logging level: DEBUG | INFO | WARNING (default: WARNING)
    RAI_MCP_HTTP_HOST                     HTTP transport bind host (default: 0.0.0.0)
    RAI_MCP_HTTP_PORT                     HTTP transport bind port (default: 8766)
    RAI_MCP_HTTP_ALLOWED_HOSTS            Comma-separated Host header allowlist for DNS
                                           rebinding protection (e.g. "mcp.example.com,
                                           mcp.example.com:*"). Empty by default — see
                                           MIGRATION_WHITEPACT_V2.md Section on transport
                                           security for why that's the safe default.
    RAI_MCP_HTTP_ALLOWED_ORIGINS          Comma-separated Origin header allowlist, same
                                           DNS rebinding protection mechanism.
    RAI_MCP_HTTP_DNS_REBINDING_PROTECTION Force-enable/disable DNS rebinding protection
                                           (true/false). Defaults to enabled automatically
                                           once either allowlist above is non-empty.
    RAI_MCP_HTTP_AUTH_MAX_FAILURES        Failed Bearer-auth attempts allowed per client
                                           IP within the window below before 429s (default: 10).
    RAI_MCP_HTTP_AUTH_WINDOW_SECONDS      Sliding window for the above, in seconds (default: 60).
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

from responsibleai import __version__
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
    from responsibleai.mcp.governance_integration import GovernanceServices
    from responsibleai.webhooks.manager import WebhookManager

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
# None unless Settings.mcp_governance_enabled is True — see that field's
# docstring and governance_integration.py's module docstring for why
# this is opt-in rather than always wired up.
_current_governance: ContextVar[GovernanceServices | None] = ContextVar(
    "_current_governance", default=None
)


def _month_start_iso() -> str:
    now = datetime.now(UTC)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


@server.list_tools()
async def _list_tools() -> list[types.Tool]:
    return TOOL_DEFS


def _text_and_structured(
    payload: dict[str, Any],
) -> tuple[list[types.TextContent], dict[str, Any]]:
    """Every tool/error payload here is a JSON-native `dict[str, Any]`
    (verified: `dispatch_tool` is typed `-> dict[str, Any]`, and every
    inline error dict below is built from string/bool/None literals) —
    safe to hand to the SDK's `structuredContent` as-is. Still returning
    the serialized `TextContent` alongside it (not replacing it) per
    MIGRATION_WHITEPACT_V2.md's structured-output section: pre-2025-06-18
    clients that only read `content` keep working unchanged.
    """
    text = types.TextContent(type="text", text=json.dumps(payload, indent=2, default=str))
    return [text], payload


@server.call_tool()
async def _call_tool(
    name: str,
    arguments: dict[str, Any] | None,
) -> tuple[list[types.TextContent], dict[str, Any]]:
    _logger.debug("tool_call name=%s args=%s", name, arguments)

    ctx = _current_org.get()
    usage_repo = _current_usage_repo.get()

    if ctx is not None:
        if not is_allowed(name, ctx.plan):
            if usage_repo is not None and ctx.org_id:
                await usage_repo.record_call(ctx.org_id, name, ctx.plan.value, allowed=False)
            error = {"error": "upgrade_required", "message": upgrade_message(name, ctx.plan)}
            return _text_and_structured(error)

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
            return _text_and_structured(error)

        if quota is not None and usage_repo is not None and ctx.org_id:
            used = await usage_repo.count_since(ctx.org_id, _month_start_iso())
            if used >= quota:
                await usage_repo.record_call(ctx.org_id, name, ctx.plan.value, allowed=False)
                error = {
                    "error": "quota_exceeded",
                    "message": quota_exceeded_message(ctx.plan, used, quota),
                }
                return _text_and_structured(error)

        if usage_repo is not None and ctx.org_id:
            await usage_repo.record_call(ctx.org_id, name, ctx.plan.value, allowed=True)

    call_arguments = arguments or {}
    governance = _current_governance.get()
    if governance is not None and ctx is not None and ctx.org_id:
        # Local import: keeps the stdio transport's import graph free of
        # the DB/governance layer unless a hosted-HTTP connection with
        # mcp_governance_enabled=True actually populated this ContextVar
        # — see governance_integration.py's module docstring.
        from responsibleai.mcp.governance_integration import apply_governance

        outcome = await apply_governance(name, call_arguments, ctx, governance)
        if not outcome.proceed:
            return _text_and_structured(outcome.blocked_response or {"error": "governance_blocked"})
        # apply_governance() already ran the tool via InternalToolExecutor
        # once it had a valid ExecutionAuthorization — outcome.result is
        # that result. Calling dispatch_tool() again here would both
        # double-execute the tool and reintroduce the exact bypass this
        # wiring exists to close.
        assert outcome.result is not None, "governed ALLOW outcome must carry an execution result"
        return _text_and_structured(outcome.result)

    result = await dispatch_tool(name, call_arguments)
    return _text_and_structured(result)


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

def _split_csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _env_bool(name: str, *, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _build_transport_security() -> Any:
    """DNS rebinding protection for both hosted transports (spec: MCP servers
    must validate Host/Origin headers to prevent a malicious webpage from
    reaching a server bound to localhost/an internal address via the
    victim's browser). Disabled by default — matching the underlying SDK's
    own backward-compatible default — unless the deployer actually
    configures an allowlist, since enabling it with empty allowlists would
    reject every request. See MIGRATION_WHITEPACT_V2.md's transport
    security section.
    """
    from mcp.server.transport_security import TransportSecuritySettings

    allowed_hosts = _split_csv(os.environ.get("RAI_MCP_HTTP_ALLOWED_HOSTS", ""))
    allowed_origins = _split_csv(os.environ.get("RAI_MCP_HTTP_ALLOWED_ORIGINS", ""))
    enabled = _env_bool(
        "RAI_MCP_HTTP_DNS_REBINDING_PROTECTION",
        default=bool(allowed_hosts or allowed_origins),
    )
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=enabled,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )


class _AuthFailureLimiter:
    """Per-process sliding-window limiter on failed Bearer-auth attempts,
    keyed by client IP — blocks credential-stuffing/brute-force probing of
    `/mcp` and `/sse` before it reaches `OrgRepository.authenticate`'s
    database round trip. Deliberately separate from `PlanRateLimiter`
    (dashboard/plan_rate_limiter.py): that one meters *successful*,
    authenticated tool calls against a billing plan; this one guards the
    auth boundary itself and has no concept of an org or plan yet.

    In-memory, so this is per-replica, not cluster-wide — same documented
    limitation as everything else in this codebase that isn't backed by
    Postgres/Redis (see `DatabaseEngine`'s docstring). A determined
    attacker distributing requests across replicas isn't stopped by this
    alone; it's a real speed bump against the common single-source case,
    not a claim of distributed rate limiting.
    """

    def __init__(self, max_failures: int, window_seconds: float) -> None:
        self._max_failures = max_failures
        self._window_seconds = window_seconds
        self._failures: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

    def _prune(self, key: str, now: float) -> list[float]:
        attempts = [t for t in self._failures.get(key, []) if now - t < self._window_seconds]
        self._failures[key] = attempts
        return attempts

    async def is_blocked(self, key: str) -> bool:
        async with self._lock:
            now = asyncio.get_running_loop().time()
            return len(self._prune(key, now)) >= self._max_failures

    async def record_failure(self, key: str) -> None:
        async with self._lock:
            now = asyncio.get_running_loop().time()
            self._prune(key, now).append(now)


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

    from responsibleai.auth.oidc import OIDCProvider
    from responsibleai.dashboard.config import get_settings
    from responsibleai.db import McpUsageRepository, OrgRepository, create_engine
    from responsibleai.rbac.models import Plan, Role
    from responsibleai.rbac.permissions import role_from_str

    settings = get_settings()
    _db_engine = create_engine(settings.effective_db_url)
    _org_repo = OrgRepository(_db_engine)
    _usage_repo = McpUsageRepository(_db_engine)

    _governance_services: GovernanceServices | None = None
    _governance_webhook_manager: WebhookManager | None = None
    if settings.mcp_governance_enabled:
        from responsibleai.db import (
            ApprovalRepository,
            EvidenceRepository,
            PolicyRepository,
            WebhookConfigRepository,
            WebhookDeliveryRepository,
        )
        from responsibleai.governance import WhitePactRuntimeGateway
        from responsibleai.integrations.client import TrustClient
        from responsibleai.mcp.governance_integration import (
            GovernanceServices as RuntimeGovernanceServices,
        )
        from responsibleai.webhooks.manager import WebhookManager as RuntimeWebhookManager

        _governance_webhook_manager = RuntimeWebhookManager()
        _governance_webhook_manager.set_repository(WebhookDeliveryRepository(_db_engine))
        _governance_webhook_manager.set_config_repository(WebhookConfigRepository(_db_engine))

        _governance_services = RuntimeGovernanceServices(
            gateway=WhitePactRuntimeGateway(),
            evidence_repo=EvidenceRepository(_db_engine),
            approval_repo=ApprovalRepository(_db_engine),
            policy_repo=PolicyRepository(_db_engine),
            trust_client=TrustClient(),
            webhook_manager=_governance_webhook_manager,
        )
    # Reuses the exact same RAI_OIDC_* / Settings.oidc_* config the
    # dashboard API's SSO login already reads (dashboard/app.py's own
    # `_oidc_provider` construction) — a Bearer JWT obtained via the
    # existing `/api/auth/login/oidc` flow authenticates here too, making
    # the hosted MCP server an OAuth/OIDC *resource server* against
    # whichever Authorization Server the org's SSO already trusts, rather
    # than a second, MCP-specific OIDC config to keep in sync.
    _oidc_provider = (
        OIDCProvider(
            issuer=settings.oidc_issuer,
            client_id=settings.oidc_client_id,
            jwks_uri=settings.oidc_jwks_uri,
            skip_verification=settings.oidc_skip_verification,
        )
        if settings.oidc_issuer
        else None
    )
    transport_security = _build_transport_security()
    sse = SseServerTransport("/messages/", security_settings=transport_security)
    # stateless=True: each POST to /mcp is authenticated and dispatched
    # independently, mirroring the legacy /sse transport's per-connection
    # Bearer auth rather than introducing cross-request session affinity.
    streamable_http = StreamableHTTPSessionManager(
        app=server, stateless=True, security_settings=transport_security,
    )
    auth_limiter = _AuthFailureLimiter(
        max_failures=int(os.environ.get("RAI_MCP_HTTP_AUTH_MAX_FAILURES", "10")),
        window_seconds=float(os.environ.get("RAI_MCP_HTTP_AUTH_WINDOW_SECONDS", "60")),
    )

    @asynccontextmanager
    async def _lifespan(_app: Starlette) -> Any:
        await _db_engine.init()
        if _governance_webhook_manager is not None:
            await _governance_webhook_manager.load_configs()
            _governance_webhook_manager.start_retry_worker()
        try:
            async with streamable_http.run():
                yield
        finally:
            if _governance_webhook_manager is not None:
                _governance_webhook_manager.stop_retry_worker()

    def _client_key(request: Request) -> str:
        return request.client.host if request.client else "unknown"

    async def _resolve_oidc_context(token: str) -> OrgContext | None:
        """Validate an OIDC-issued Bearer JWT and map its claims to an
        OrgContext — same logic as dashboard/app.py's `_resolve_oidc_context`.
        Static API keys are prefixed `rai_` (see `_generate_raw_key` in
        org_repository.py); anything else is attempted as a JWT when an
        OIDC provider is configured, so a JWT and a static key are never
        ambiguous."""
        if _oidc_provider is None or token.startswith("rai_"):
            return None
        try:
            claims = await _oidc_provider.validate_token(token)
        except ValueError:
            return None

        org = await _org_repo.get_org(claims.org_id) if claims.org_id else None
        role = Role.VIEWER
        for raw_role in claims.roles:
            candidate = role_from_str(raw_role)
            if candidate.value == raw_role.upper():
                role = candidate
                break

        return OrgContext(
            key_id=f"oidc:{claims.sub}",
            role=role,
            org_id=claims.org_id,
            org_name=org.name if org else None,
            is_legacy=False,
            plan=org.plan if org else Plan.FREE,
        )

    async def _authenticate(request: Request) -> OrgContext | None:
        if settings.mcp_http_allow_unauthenticated_demo:
            # DANGER — demo/recording use only, see config.py's field
            # docstring. Grants read-only access with no key at all.
            # Plan.ENTERPRISE (not FREE): FREE gets zero hosted quota by
            # design (see licensing.py MONTHLY_CALL_QUOTA), which would
            # block a reviewer from exercising the full tool surface —
            # the opposite of what a demo should show. Role stays
            # VIEWER (read-only) regardless; plan and role are separate
            # axes, so this doesn't grant any write/admin capability.
            return OrgContext(key_id="demo:unauthenticated", role=Role.VIEWER, is_legacy=True, plan=Plan.ENTERPRISE)
        auth_header = request.headers.get("authorization", "")
        if not auth_header.lower().startswith("bearer "):
            return None
        raw_key = auth_header[7:].strip()
        if not raw_key:
            return None
        oidc_ctx = await _resolve_oidc_context(raw_key)
        if oidc_ctx is not None:
            return oidc_ctx
        return await _org_repo.authenticate(raw_key)

    def _protected_resource_metadata_url(request: Request) -> str:
        return str(request.url.replace(path="/.well-known/oauth-protected-resource", query=""))

    async def _authenticate_or_error(request: Request) -> tuple[OrgContext | None, JSONResponse | None]:
        """Bearer auth gated by `auth_limiter`: blocks a client IP that's
        already exhausted its failure budget *before* touching the DB, then
        records a fresh failure on rejection. Shared by both hosted
        transports so a probe against one doesn't get a bigger budget by
        switching to the other."""
        client_key = _client_key(request)
        if await auth_limiter.is_blocked(client_key):
            return None, JSONResponse(
                {
                    "error": "too_many_attempts",
                    "message": "Too many failed authentication attempts from this client. Try again later.",
                },
                status_code=429,
            )
        ctx = await _authenticate(request)
        if ctx is None:
            await auth_limiter.record_failure(client_key)
            headers = {}
            if _oidc_provider is not None:
                # RFC 9728 / MCP Authorization spec: point an OAuth-aware
                # client at where to discover the Authorization Server,
                # instead of leaving it to guess. Only advertised when an
                # OIDC provider is actually configured — advertising it
                # unconditionally would tell every client "use OAuth" even
                # for deployments that only support static API keys.
                headers["WWW-Authenticate"] = (
                    f'Bearer resource_metadata="{_protected_resource_metadata_url(request)}"'
                )
            return None, JSONResponse(
                {"error": "unauthorized", "message": "Provide a valid Bearer API key."},
                status_code=401,
                headers=headers,
            )
        return ctx, None

    async def handle_sse(request: Request) -> Any:
        ctx, error = await _authenticate_or_error(request)
        if error is not None:
            return error

        org_token = _current_org.set(ctx)
        usage_token = _current_usage_repo.set(_usage_repo)
        governance_token = _current_governance.set(_governance_services)
        try:
            async with sse.connect_sse(
                request.scope, request.receive, request._send
            ) as (read_stream, write_stream):
                init_options = server.create_initialization_options()
                await server.run(read_stream, write_stream, init_options)
        finally:
            _current_org.reset(org_token)
            _current_usage_repo.reset(usage_token)
            _current_governance.reset(governance_token)
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
            ctx, error = await _authenticate_or_error(request)
            if error is not None:
                await error(scope, receive, send)
                return

            org_token = _current_org.set(ctx)
            usage_token = _current_usage_repo.set(_usage_repo)
            governance_token = _current_governance.set(_governance_services)
            try:
                await streamable_http.handle_request(scope, receive, send)
            finally:
                _current_org.reset(org_token)
                _current_usage_repo.reset(usage_token)
                _current_governance.reset(governance_token)

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

    async def protected_resource_metadata(request: Request) -> JSONResponse:
        """RFC 9728 Protected Resource Metadata. 404 when no OIDC provider
        is configured — this deployment then only supports static API
        keys, and there's no Authorization Server to point a client at."""
        if _oidc_provider is None:
            return JSONResponse({"error": "not_found"}, status_code=404)
        resource_url = str(request.url.replace(path="/mcp", query=""))
        return JSONResponse({
            "resource": resource_url,
            "authorization_servers": [settings.oidc_issuer],
            "bearer_methods_supported": ["header"],
        })

    async def mcp_server_card(request: Request) -> JSONResponse:
        """Static capability card for directories (e.g. Smithery) that
        can't complete a live authenticated scan against /mcp — this
        deployment has no OAuth authorization server configured (see
        protected_resource_metadata above), only static Bearer API
        keys, which a directory's automated crawler can't obtain on
        its own. Bypasses live scanning per the directory's own
        documented fallback rather than leaving the listing unscanned.
        Tool/resource data is generated from the same TOOL_DEFS/
        RESOURCE_DEFS the live server itself advertises — never a
        separately maintained, driftable copy."""
        return JSONResponse({
            "serverInfo": {"name": "whitepact", "version": __version__},
            "authentication": {
                "required": True,
                "schemes": ["apiKey"],
            },
            "tools": [
                t.model_dump(mode="json", exclude_none=True, by_alias=True) for t in TOOL_DEFS
            ],
            "resources": [
                r.model_dump(mode="json", exclude_none=True, by_alias=True) for r in RESOURCE_DEFS
            ],
            "prompts": [],
        })

    app = Starlette(
        routes=[
            Route("/health", endpoint=health),
            Route("/mcp", endpoint=handle_streamable_http),
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
            Route("/.well-known/oauth-protected-resource", endpoint=protected_resource_metadata),
            Route("/.well-known/mcp/server-card.json", endpoint=mcp_server_card),
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
