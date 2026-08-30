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

import hashlib
from typing import TYPE_CHECKING, Any, Protocol

import httpx

from responsibleai.governance.execution import (
    ExecutionAuthorization,
    NonceConsumer,
    _validate_authorization,
    check_target_fingerprint,
    consume_nonce_durably,
)
from responsibleai.governance.jit_credential import consume_jit_credential, issue_jit_credential
from responsibleai.governance.models import ActionRequest
from responsibleai.governance.risk import UPSTREAM_ACTION_TYPE
from responsibleai.governance.upstream import validate_upstream_server_url

ACTION_TYPE = UPSTREAM_ACTION_TYPE

if TYPE_CHECKING:
    from responsibleai.db.credential_issuance_repository import CredentialIssuanceRepository
    from responsibleai.db.upstream_repository import UpstreamServerRepository
    from responsibleai.governance.upstream import UpstreamServer

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


def compute_upstream_target_fingerprint(server: UpstreamServer) -> str:
    """Execution Permit v2 (Authority Everywhere Phase 9): a hash of
    everything about *server* that would change what actually happens
    if a call is proxied to it — its URL, whether it's enabled, and
    whether a credential is attached (not the credential value itself;
    ``ExecutionAuthorization`` must never carry a secret). ``server_id``
    is deliberately excluded — it's already covered by
    ``action.target``, and a permit should catch the config *behind* an
    unchanged server_id drifting, not merely restate the ID. Computed
    fresh both when the gateway authorizes a call
    (``mcp/upstream_dispatch.py``) and again immediately before dispatch
    (this module's own ``execute()``) — a mismatch means the server's
    registration changed in between, and the permit no longer describes
    what it originally authorized."""
    payload = f"{server.url}|{server.enabled}|{server.auth_token is not None}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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
        credential_issuance_repo: CredentialIssuanceRepository | None = None,
        nonce_repo: NonceConsumer | None = None,
    ) -> None:
        self._registry = registry
        # Enterprise Readiness Phase 4 (replay protection) -- optional,
        # same backward-compatible-None pattern as
        # credential_issuance_repo below. Constructed per-call in this
        # executor's case (unlike InternalToolExecutor's module-level
        # singleton), so a real one is simply passed at construction
        # time by every call site that has DB access -- no late-binding
        # setter needed here.
        self._nonce_repo = nonce_repo
        # Resolved at call time (execute()), not bound here as a default
        # parameter value -- a default value captures a reference to
        # whatever _default_http_client_factory *was* at class-
        # definition/import time, so monkeypatching the module-level
        # name later (the standard test seam for "swap this for a
        # fake") would silently have no effect. None here just means
        # "use whatever the module-level name currently points to."
        self._http_client_factory = http_client_factory
        # Optional -- audit persistence for the JIT Credential Broker
        # (Phase 10). None is a valid, backward-compatible configuration
        # (e.g. an executor used only in a unit test with no DB): the
        # credential is still issued and consumed correctly, it just
        # isn't recorded anywhere. Every call site this platform itself
        # controls (dashboard/app.py) does supply one.
        self._credential_issuance_repo = credential_issuance_repo

    async def execute(self, authorization: ExecutionAuthorization, action: ActionRequest) -> Any:
        # Same precedence InternalToolExecutor uses: the authorization's
        # own shape (consumed/expired/org/action-match) is checked
        # before anything about the target is even looked up, so a
        # stale or forged authorization is rejected on its own terms
        # rather than on an incidental "server not found."
        _validate_authorization(authorization, action)
        await consume_nonce_durably(authorization, self._nonce_repo)

        server_id, tool_name = parse_upstream_target(action.target)
        server = await self._registry.get(server_id)
        if server is None or server.org_id != action.agent.organization_id or not server.enabled:
            raise UpstreamServerNotAvailableError(server_id)

        # Execution Permit v2 -- only after the target actually resolves
        # can it be compared against what was fingerprinted at decision
        # time; see check_target_fingerprint()'s own docstring for why
        # this must be a separate step from _validate_authorization().
        check_target_fingerprint(authorization, compute_upstream_target_fingerprint(server))

        # JIT Credential Broker (Phase 10) -- the executor no longer
        # reads server.auth_token directly. It asks
        # governance/jit_credential.py for a single-use, time-boxed
        # credential bound to this exact authorization, records that
        # issuance (fail-open, audit-only), then consumes it for
        # exactly this one call. See jit_credential.py's module
        # docstring for what this does and does not narrow. Issued
        # *before* the authorization itself is marked consumed below --
        # issue_jit_credential() requires a still-valid authorization,
        # by design (a credential's trust rests on the permit's
        # validity at issuance time).
        credential = issue_jit_credential(authorization, server_id, server)
        if self._credential_issuance_repo is not None:
            await self._credential_issuance_repo.record_issued(
                credential, action_id=action.action_id, agent_id=action.agent.agent_id
            )

        authorization.consumed = True  # single-use, same as InternalToolExecutor

        auth_token = consume_jit_credential(credential)
        if self._credential_issuance_repo is not None:
            await self._credential_issuance_repo.record_consumed(credential.credential_id)

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
            auth_token=auth_token,
        )
