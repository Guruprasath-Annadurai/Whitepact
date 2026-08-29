"""Heart Production Closure Gap C — fail-fast production-authority-
enforced startup invariant.

**The gap this closes, per `docs/heart-production-closure/
00_CLOSURE_AUDIT.md`**: `Settings.enterprise_mode=true` already gates
crypto activation (`db/crypto_activation.py`, Security Remediation Gap
1) with real fail-closed startup behavior — but it does NOT gate Heart
legitimacy enforcement at all. A deployment could set
`enterprise_mode=true` (believing it has switched on "production
fail-closed behavior") while `mcp_governance_enabled` stays at its
default `False`, in which case the audit's traced bypass path #1
applies unchanged: `_call_tool()`'s governance branch is never taken,
every tool call reaches `_dispatch_tool_unchecked()` with zero governance, and
Heart is never consulted regardless of `enterprise_mode`. That is a
silent, easy-to-hit misconfiguration for exactly the deployment most
likely to believe it is protected.

**The design choice made here, and why**: the directive's own Gap C
guidance says to introduce a new `LEGACY`/`HEART_OPTIONAL`/
`HEART_ENFORCED` mode enum "only if cleaner than existing architecture
— do not introduce this exact enum if existing configuration already
provides a better representation." `enterprise_mode` already exists,
is already documented as "enable enterprise/production fail-closed
behavior," and already has exactly this fail-fast-at-startup precedent
(crypto activation). Extending it — requiring `enterprise_mode=true`
to also imply `mcp_governance_enabled=true` and live Heart-dependency
reachability — is that better representation; a parallel enum would
create two competing "is this production" flags in the same codebase.

**What this module does and does not do**:

- **Does** fail startup (raise, before the first request is served)
  when `enterprise_mode=true` and any of: `mcp_governance_enabled` is
  false, the root-authority repository is unreachable, the
  revocation-epoch repository is unreachable, or (Heart Enforcement
  Chokepoint Closure Phase E4) `mcp_http_allow_unauthenticated_demo` is
  true. This is the literal `production_authority_mode=true + Heart
  unavailable/misconfigured = startup failure` invariant the directive
  names, using `enterprise_mode` as that mode flag.
- **Critical wiring fix (Phase E0/E4)**: this function previously ran
  ONLY from `dashboard/app.py`'s own startup -- the separate
  `whitepact-mcp-http` process (`mcp/server.py`'s `_build_http_app()`
  `_lifespan()`) never called it at all, meaning the fail-closed
  startup invariant this module exists to provide never actually
  protected the one process where stdio-block/legacy-key/demo-auth
  bypasses live. Now called from both processes' startup.
- **Does not** claim every alternate execution path this codebase has
  is closed. The audit traced six, now down to one genuinely open item:
  (1) `mcp_governance_enabled=False` (closed by this gate — enforced
  mode now requires it true); (2) `enterprise_mode` was itself the
  second independent opt-in Heart needed (closed — this gate makes it
  imply governance); (3) the self-hosted stdio transport (closed
  separately -- Phase E2, see `mcp/server.py`'s `_call_tool()` --
  enterprise_mode now blocks stdio entirely rather than needing a
  startup check here); (4) legacy non-org-scoped API keys reaching
  hosted-MCP dispatch ungoverned (**corrected, not real** -- the
  original audit's claim here was a factual error; see
  `ENFORCEMENT_PATH_MATRIX.md`'s Path 4 correction. The demo-auth flag
  it was conflated with is real and is closed above); (5) a direct
  Python import of `mcp.tools._dispatch_tool_unchecked()` bypassing the
  HTTP layer entirely (**mitigated, not fully closeable** by a runtime
  startup check -- it is a structural property of that function having
  no caller-identity concept of its own. Phase E5 renamed it from
  `dispatch_tool` to `_dispatch_tool_unchecked`, so it is no longer
  accidentally indistinguishable from a safe public entrypoint, and
  `tests/test_dispatch_tool_unchecked_call_sites.py` fails the suite if
  a new internal call site appears anywhere this audit didn't account
  for. A determined caller with repo access can still import and call
  a private function directly -- Python cannot prevent that -- named
  honestly rather than claimed impossible).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from responsibleai.db.engine import governance_revocation_epochs, governance_root_authority_records

if TYPE_CHECKING:
    from responsibleai.dashboard.config import Settings
    from responsibleai.db.engine import DatabaseEngine


class HeartEnforcementError(RuntimeError):
    """Raised when `enterprise_mode=true` but Heart production
    enforcement cannot actually be guaranteed -- the caller must let
    this propagate and abort startup, never catch-and-continue with a
    deployment that believes it is enforcing Heart legitimacy but
    isn't."""


async def verify_heart_production_enforcement(settings: Settings, engine: DatabaseEngine) -> None:
    """Call once at application startup, after the database engine and
    migrations are ready, before the first request is served. No-op
    when `settings.enterprise_mode` is falsy, exactly mirroring
    `activate_production_crypto()`'s own gating -- development/
    self-hosted behavior is completely unchanged.

    Raises `HeartEnforcementError` (fail-closed) if `enterprise_mode`
    is true but Heart's required production dependencies are not all
    genuinely available. Never catches its own exceptions -- the
    caller (application startup) must let this abort the process.
    """
    if not settings.enterprise_mode:
        return

    if not settings.mcp_governance_enabled:
        raise HeartEnforcementError(
            "enterprise_mode=true requires mcp_governance_enabled=true. "
            "Heart legitimacy is only ever consulted on the hosted-MCP "
            "dispatch path when governance dispatch-gating itself is on -- "
            "enterprise_mode=true with mcp_governance_enabled=false would "
            "silently run zero governance on every tool call while the "
            "deployment believes it is enforcing production authority. "
            "Set mcp_governance_enabled=true, or unset enterprise_mode if "
            "this deployment intentionally does not enforce Heart yet."
        )

    if settings.mcp_http_allow_unauthenticated_demo:
        raise HeartEnforcementError(
            "enterprise_mode=true is incompatible with "
            "mcp_http_allow_unauthenticated_demo=true. The demo flag grants "
            "hosted MCP access with no credential at all, over a connection "
            "the governance dispatch path (mcp/server.py's _call_tool()) "
            "cannot build an AuthorityContext for -- every tool call over "
            "that connection reaches _dispatch_tool_unchecked() with zero governance "
            "and zero Heart legitimacy check, regardless of enterprise_mode. "
            "Unset mcp_http_allow_unauthenticated_demo before enabling "
            "enterprise_mode, or unset enterprise_mode if this deployment "
            "intentionally runs the demo flag."
        )

    try:
        async with engine.raw.connect() as conn:
            await conn.execute(select(governance_root_authority_records.c.root_id).limit(1))
    except Exception as exc:
        raise HeartEnforcementError(
            "enterprise_mode=true requires the root-authority store to be "
            f"reachable at startup; the readiness query failed: {exc!r}. "
            "Heart legitimacy resolution cannot fail closed per-request if "
            "its own backing store is unavailable -- refusing to start "
            "rather than serving traffic that would silently skip root "
            "validation."
        ) from exc

    try:
        async with engine.raw.connect() as conn:
            await conn.execute(select(governance_revocation_epochs.c.organization_id).limit(1))
    except Exception as exc:
        raise HeartEnforcementError(
            "enterprise_mode=true requires the revocation-epoch store to "
            f"be reachable at startup; the readiness query failed: {exc!r}."
        ) from exc
