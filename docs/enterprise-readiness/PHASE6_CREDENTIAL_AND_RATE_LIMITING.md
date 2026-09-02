# Phase 6 — Credential Scoping/Rotation + Auth Rate-Limiting Coverage

**Directive**: WHITEPACT — FULL ENTERPRISE PRODUCTION + PUBLIC LAUNCH
CLOSURE MASTER DIRECTIVE, Phase 6.

## What this phase delivered

1. **Credential scoping/rotation policy**:
   [`docs/security/CREDENTIAL_SCOPING_AND_ROTATION.md`](../security/CREDENTIAL_SCOPING_AND_ROTATION.md)
   — every credential type this platform actually issues (static API
   keys, legacy flat keys, OIDC JWTs, SAML assertions, TOTP MFA
   secrets/backup codes), how each is scoped, what rotation each
   genuinely supports today, and what doesn't exist yet (no automated
   API key expiry — named as a real gap with a concrete recommended
   follow-up, not hidden).

2. **Auth rate-limiting coverage beyond the MCP-specific limiter**:
   `mcp/server.py`'s `_AuthFailureLimiter` protected only the hosted
   MCP transport (`/mcp`, `/sse`); the REST dashboard API's existing
   slowapi rate limiting keys by the *presented* Bearer token when one
   is present — a real gap, since an attacker trying many *different*
   candidate tokens against any Bearer-protected REST endpoint got a
   fresh, unthrottled bucket for every guess. Closed with a new
   `AuthFailureLimiter` (`dashboard/middleware.py`), same design as the
   MCP transport's own, wired into `get_org_context()`: 20 failed
   attempts per IP per 60-second window, checked before credential
   resolution starts.

## Verification

`tests/test_rest_auth_failure_limiter.py`, 5 tests, all passing:
- Valid keys are never throttled by this mechanism (30 consecutive
  successful calls, zero 429s).
- 25 distinct *different* wrong guesses correctly trip the limiter —
  proving this isn't per-token bucketing (the exact gap being closed).
- A blocked IP stays blocked even for a subsequently-presented *valid*
  key (fail-closed, matching the MCP transport's own behavior).
- Missing-Authorization-header attempts count as failures too.
- `auth_enabled=False` (dev mode) bypasses the limiter entirely,
  matching every other auth mechanism's dev-mode bypass.

Full regression run (`test_dashboard_api.py`, `test_governance_api.py`,
`test_org_api.py`, `test_rbac.py`, `test_mfa*.py`, `test_signup.py`,
`test_redteam_audit_billing_api.py`, `test_cross_tenant_isolation_sweep.py`,
`test_public_api_fuzz.py`): 382 passed, 0 failed — the new limiter's
20/minute threshold doesn't interfere with any existing test's request
volume.

`ruff check` / `mypy src/responsibleai`: clean.

## Phase 6 verdict

**READY TO ADVANCE.** Both named gaps closed with real, tested
mechanisms — not documentation alone.
