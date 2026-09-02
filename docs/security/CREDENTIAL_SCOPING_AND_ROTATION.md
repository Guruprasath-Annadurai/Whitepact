# Credential Scoping and Rotation Policy

**Directive**: WHITEPACT — FULL ENTERPRISE PRODUCTION + PUBLIC LAUNCH
CLOSURE MASTER DIRECTIVE, Phase 6. `00_MASTER_READINESS_AUDIT.md`'s
Authentication row named the gap: credential scoping/rotation policy
was never written down, and auth rate-limiting only covered the hosted
MCP transport, not the REST API.

This document describes every credential type this platform actually
issues, how each is scoped, and what rotation/expiry each one
genuinely supports today — grounded in the real code
(`db/org_repository.py`, `auth/oidc.py`, `auth/saml.py`,
`auth/mfa.py`), not aspirational. Where a mechanism doesn't exist yet,
that's stated as a gap, not implied to exist.

## Credential types

### 1. Static API keys (`org_api_keys` table)

**Scoping**: every key belongs to exactly one organization and carries
exactly one `Role` (`OWNER` > `ADMIN` > `ANALYST` > `VIEWER`,
`rbac/models.py`) — there is no cross-org key and no key with more
than one role. A key's role is fixed at creation
(`OrgRepository.create_key()`); changing a key's role means revoking
it and issuing a new one, not editing the existing row.

**Storage**: hashed at rest (SHA-256, `db/org_repository.py`'s
`_hash_key()`) — the raw key is returned exactly once, at creation
time, and never stored or logged in plaintext anywhere (verified by
this session's own prior work, `tests/test_crypto_activation.py::TestSecretsNeverAppearInLogs`,
though that test's coverage is scoped to crypto activation specifically
— see the "Known gap" note below).

**Rotation**: `OrgRepository.revoke_key()` exists;
**no automatic expiry exists** — a static API key is valid forever
until an admin explicitly revokes it. This is a real, honest gap, not
a rotation *policy* failure: the mechanism to revoke-and-reissue exists
today (`DELETE /api/orgs/{org_id}/keys/{key_id}` +
`POST /api/orgs/{org_id}/keys`); what doesn't exist is any
*automated* expiry, reminder, or forced-rotation schedule.

**Recommended operational policy** (process, not enforced by code
today):
- Rotate every static API key at least every 90 days for ENTERPRISE-tier
  orgs, every 180 days otherwise — track this externally (a calendar
  reminder, a ticket) until an automated expiry field exists (see
  "Recommended follow-up" below).
- Revoke immediately on personnel offboarding or suspected compromise
  — `DELETE /api/orgs/{org_id}/keys/{key_id}` takes effect on the very
  next request (no cache, confirmed by direct grep in this session's
  earlier Heart Production Closure work).
- Never share one API key across multiple humans or services — issue
  one key per distinct caller so revocation of one doesn't affect
  others, and so `AgentContext.agent_id`-scoped audit trails
  (evidence records, quarantine tracking) stay attributable to one
  actual actor.
- Prefer the minimum role that accomplishes the task — `VIEWER` for
  read-only integrations, `ANALYST` for governed tool-calling agents
  that don't need to manage other keys or policy, `ADMIN`/`OWNER`
  reserved for humans doing account administration.

### 2. Legacy flat keys (`RAI_API_KEYS` env var)

**Scoping**: none — a legacy flat key is a self-hosted, single-tenant
"super-admin" credential (`OrgContext(role=Role.OWNER, is_legacy=True)`),
with no `org_id` at all, deliberately (this is the same persona that
`list_webhooks()`/`list_incidents()`/every `/api/orgs/{org_id}/...`
handler's `_require_caller_owns_org()` guard (Phase 7) exempts —
see `PHASE7_CROSS_TENANT_ISOLATION.md`).

**Rotation**: entirely the deployer's own responsibility — this is a
raw environment variable, not a database row this platform can revoke
or expire on its own. **Recommended policy**: do not use flat keys for
anything beyond initial bootstrap/self-hosted single-operator
deployments; issue a real org-scoped `OWNER` key via
`POST /api/orgs/{org_id}/keys` as soon as an org exists, and stop
setting `RAI_API_KEYS` in production once that's done.

### 3. OIDC-issued JWTs

**Scoping**: role/org resolved from token claims at request time
(`auth/oidc.py`) — no long-lived platform-issued credential at all,
the IdP's own token *is* the credential.

**Rotation**: handled entirely by the configured IdP's own token
lifetime and refresh-token flow — this platform only validates
`exp`/signature/audience per request (`ValueError("Token has expired")`
on an expired token, confirmed in `auth/oidc.py`) and never extends or
caches validity beyond what the IdP itself asserts. Rotation policy for
OIDC is therefore the IdP administrator's policy, not something this
platform's own docs can set.

### 4. SAML assertions

**Scoping**: SAML has no bearer-token concept (unlike OIDC) — a
consumed assertion isn't a repeatable API credential
(`ENTERPRISE_SECURITY.md`'s own SAML section). A successful SAML login
mints a short-lived (1 hour), HMAC-signed platform session token
instead.

**Rotation**: the 1-hour session token expiry is fixed and short by
design — no rotation policy needed beyond "re-authenticate via the IdP
when it expires," which is the normal SAML SSO flow.

### 5. TOTP MFA secrets and backup codes

**Scoping**: per-API-key, not per-org — each key enrolls its own TOTP
secret (`auth/mfa.py`); enrolling one key's MFA has no effect on any
other key in the same org.

**Rotation**: `POST .../mfa/enroll` (re-)generates a fresh secret
before verification — calling it again before verifying replaces the
pending secret (confirmed in `dashboard/app.py`'s `enroll_mfa()`
docstring). Backup codes are one-time-use (consumed on use) and are
shown exactly once at generation; there is no "regenerate backup codes
only" endpoint today — full disable-then-re-enroll is the only way to
get a fresh set. **Recommended policy**: treat MFA re-enrollment the
same as a password reset — required after any suspected device loss,
not on a fixed schedule.

## Auth rate limiting — now covers both transports

**Before this phase**: only the hosted MCP transport
(`mcp/server.py`'s `_AuthFailureLimiter`) had IP-keyed brute-force
protection on failed auth attempts. The REST dashboard API's existing
slowapi rate limiting keys by the *presented* Bearer token when one is
present (`_get_rate_limit_key()`'s own docstring: deliberate, for
legitimate per-org quota isolation) — which meant an attacker trying
many *different* candidate tokens against any Bearer-protected REST
endpoint got a fresh, unthrottled bucket for every guess.

**Now**: `dashboard/middleware.py`'s new `AuthFailureLimiter` (same
design as the MCP transport's own, deliberately duplicated rather than
shared across the stdio/HTTP import boundary — see that class's own
docstring) is wired into `get_org_context()` — 20 failed attempts per
IP per 60-second window, checked before any credential resolution
starts, recorded on every failure path (missing header, unresolvable
token). A blocked IP gets 429 even if it eventually presents a *valid*
key, matching the MCP transport's own fail-closed behavior. Verified
in `tests/test_rest_auth_failure_limiter.py`: valid keys are never
throttled by this mechanism (30 consecutive successful calls, no
429s); 25 distinct wrong guesses (deliberately using a *different*
candidate token each time, to prove this isn't per-token bucketing)
correctly trip the limiter; a blocked IP is blocked even for a
subsequently-presented valid key; `auth_enabled=False` (dev mode)
bypasses the limiter entirely, matching every other auth mechanism's
dev-mode bypass.

Both limiters share the same honest, documented limitation: in-memory,
per-replica, not cluster-wide. A determined attacker distributing
requests across multiple replicas isn't stopped by either alone.

## Known gap: secrets-never-logged coverage

`tests/test_crypto_activation.py::TestSecretsNeverAppearInLogs` proves
the crypto root key is never logged. No equivalent test sweep exists
for API keys, OIDC/SAML secrets, webhook signing secrets, or MFA
secrets/backup codes across every module that handles them. See
`PRODUCTION_CONFIGURATION_STANDARD.md` (Phase 9) for the extended test
coverage this phase adds for that gap.

## Recommended follow-up (not done in this phase)

- **Automated API key expiry**: add an optional `expires_at` column to
  `org_api_keys`, defaulting to unset (unlimited, current behavior) for
  backward compatibility, with an opt-in per-key or per-org maximum
  lifetime an admin can configure — the same additive,
  backward-compatible pattern this codebase already uses for every
  other optional field added this session (Phase 5's `purpose`, Phase
  3's `consent_reference`, etc.).
- **Rotation reminders**: a scheduled job (or a dashboard banner)
  surfacing keys older than the recommended rotation window.
- **Backup-code regeneration** without a full MFA disable/re-enroll
  cycle.
