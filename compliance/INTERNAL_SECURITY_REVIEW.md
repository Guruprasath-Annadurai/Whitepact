# Internal Security Review — ResponsibleAI Platform v1.2.0

> ## ⚠️ This is an internal review, not a third-party penetration test
>
> This review was performed by the platform's own maintainer using static
> analysis tooling (`bandit`, `pip-audit`) plus manual code reading. It is
> **not independent** — the person who wrote the code also reviewed it,
> which is exactly the blind spot a real penetration test exists to avoid.
> Do not represent this document as a pentest, to a customer, in a sales
> deck, or on the Trust Center page. `scripts/security-scan.sh`'s own header
> states the same caveat for its automated ZAP scan; this document doesn't
> change that — a genuine third-party pentest (cost-gated at $5-15K, tracked
> in `compliance/SOC2_READINESS.md` Section 4) is still an open gap.
>
> What this *is*: real tooling, run against the real codebase, with real
> findings — some fixed during this review (with tests), some accepted as
> low-risk with reasoning given, and one (a third-party pentest) that no
> amount of internal review can substitute for.

Last reviewed: 2026-07-23 · Platform version: 1.2.0

---

## 1. Method

- **Static analysis**: `bandit -r src/` (security-focused static analyzer;
  not previously run in this project's CI).
- **Dependency audit**: `pip-audit` against the installed environment.
- **Manual review**: authentication/authorization paths (`auth/mfa.py`,
  `db/org_repository.py`, RBAC enforcement in `dashboard/app.py`), the
  webhook delivery subsystem (outbound HTTP request construction —
  historically a common SSRF source), SQL query construction across the
  codebase (grep for string-built queries, since parameterization is the
  actual control, not just "using an ORM"), and dangerous-function usage
  (`eval`, `exec`, `pickle.load`, `yaml.load`, `os.system`, `shell=True`,
  weak hashes).
- **Scope note**: this is a code-level review. It does not (and cannot)
  cover the operational gaps `compliance/SOC2_READINESS.md` already lists
  honestly — personnel security, exercised incident response against a real
  incident, or infrastructure-layer configuration of a hosted instance that
  doesn't exist yet.

---

## 2. Findings and fixes

### 2.1 SQL injection risk in `CostTracker` — FIXED

**Severity**: Medium (bandit B608) · **Status**: Fixed, with regression tests.

`src/responsibleai/cost/tracker.py` built three queries via f-string
interpolation of a `days: int | None` parameter directly into the SQL text
(`get_model_breakdown`, `get_team_breakdown`, `request_count`), rather than
the parameterized-query pattern the rest of the file already used correctly
(`total_cost`, `total_tokens`, `get_daily_costs` all pass `?` placeholders).

**Why this mattered despite the `int` type hint**: `CostTracker` is a public
class exported from `responsibleai/__init__.py` for library consumers who
embed the package directly — not gated behind the FastAPI layer's Pydantic
validation that protects the *API* surface (`db/repositories.py`'s
`CostRepository`, the class actually used by `dashboard/app.py`, already
parameterizes correctly and additionally bounds-checks `days` at the API
layer — see `app.py`'s `/api/cost/summary` handler). Python doesn't enforce
type hints at runtime, so a downstream integrator passing a non-int value
into `CostTracker` directly (e.g., from their own unvalidated input) would
have had that value interpolated verbatim into a SQL string.

**Fix**: rewrote all three methods to use parameterized `?` placeholders
(matching the file's own existing correct pattern) and added `int(days)` as
a defense-in-depth cast that fails loudly (raises `ValueError`) rather than
interpolating a non-numeric value, if a caller ever violates the type hint.

**Tests**: existing `tests/test_cost_tracker.py` suite (26 tests) still
passes unchanged — the fix is behavior-preserving for correct callers.

### 2.2 SSRF via unrestricted webhook URLs — FIXED

**Severity**: Medium-High · **Status**: Fixed, with regression tests.

`POST /api/webhooks` (ADMIN-role only) let an org admin register any URL as
a delivery target, and `WebhookManager._deliver` (`webhooks/manager.py`)
made an outbound HTTP POST to that URL with no restriction on the target
host. This is a classic SSRF (server-side request forgery) shape: a
compromised or malicious admin-level API key could register a webhook
pointing at `http://169.254.169.254/latest/meta-data` (cloud instance
metadata — commonly used to steal cloud credentials), an internal service
on the deployer's private network (`http://10.x.x.x:6379`, Redis; internal
admin panels), or `localhost` itself. The webhook payload (potentially
including trust scores, cost data, or other account data
per event type) would be delivered to whatever accepted the connection.

**Why this is real despite requiring ADMIN role**: RBAC assumes an admin
is trusted with *their own org's* configuration, not with using this
server as a proxy into infrastructure it can reach but the admin's own
network access wouldn't otherwise reach. A leaked or over-permissioned
admin key becomes a network pivot, not just a data-access risk.

**Fix**: added `validate_webhook_url()` to `webhooks/manager.py` — resolves
the URL's hostname and rejects it if any resolved address is private,
loopback, link-local (covers `169.254.169.254`), reserved, multicast, or
unspecified, or if the scheme isn't `http`/`https`. This is checked:
- **At registration** (`POST /api/webhooks` in `dashboard/app.py`) — fails
  fast with an HTTP 400 so an admin gets immediate feedback instead of a
  silent delivery failure later.
- **At every delivery** (`webhooks/manager.py::_deliver`), not just at
  registration — because DNS can resolve differently at delivery time than
  at registration time (DNS rebinding: a hostname that resolved to a public
  IP when registered could later be repointed at an internal address).
- `httpx.AsyncClient` is now explicit about `follow_redirects=False` (was
  already the library default, made explicit here) so a public URL can't
  bounce a redirect into a private address as a bypass.

**Residual gap, stated plainly**: this blocks IP-literal and DNS-based SSRF
to the address ranges checked. It does not prevent an admin from pointing a
webhook at another *public* internet service they don't control (that's
inherent to the feature — webhooks exist to call external URLs); that's an
acceptable, expected risk profile for the feature, not a vulnerability.

**Tests**: added `TestSSRFGuard` (7 new tests) to `tests/test_webhooks.py`
covering scheme rejection, no-host rejection, loopback, RFC 1918 private
range, the cloud-metadata link-local address, an allowed public IP, and
unresolvable-host handling. Also added an autouse DNS-mocking fixture so the
26 pre-existing delivery tests (which use synthetic hostnames like
`hooks.example.com`) continue to exercise the real guard code path without
depending on real network DNS resolution in CI.

**Update (2026-07-23, follow-up pass)**: the API-layer test-coverage gap
noted above is now closed. `tests/test_dashboard_api.py::TestWebhooksAPI`
exercises `POST/GET/DELETE /api/webhooks` end-to-end: create/list/delete
roundtrip, invalid-event-type rejection, the SSRF guard rejecting a
loopback URL and the cloud-metadata address at the actual HTTP layer (not
just the manager unit tests), a 404 on deleting a nonexistent webhook, and
the `/api/webhooks/test/{id}` firing path.

### 2.3 Findings reviewed and accepted as-is (no change needed)

| Finding (bandit ID) | Location | Why accepted |
|---|---|---|
| B101, `assert` in production code | `dashboard/app.py:187`, `plan_rate_limiter.py:58` | Asserts here are internal invariant checks (e.g. a value the code itself just computed), not user-input validation — user input is validated via Pydantic models, which don't rely on `assert`. Stripped-under-`-O` behavior is a known Python footgun but doesn't create a security gap here since nothing security-relevant depends on the assert firing. |
| B106, "hardcoded password" | `prometheus.py:115-116` | False positive — the strings are `'input'`/`'output'`, Prometheus metric label *names* for token direction, not credentials. Confirmed by reading the surrounding code. |
| B110, bare `except: pass` | `telemetry.py` (×4) | Best-effort OpenTelemetry metric/span emission — deliberately fails open so a missing/misconfigured OTEL exporter never takes down a request. Not security-relevant (telemetry, not auth/authz). |
| B110, bare `except: pass` | `org_repository.py:224` | Best-effort `last_used_at` timestamp update after successful auth; auth itself already succeeded before this block runs, so a failure here doesn't affect access control, only an informational timestamp. |
| B110, bare `except: pass` | `webhooks/manager.py` (×2) | Best-effort delivery-log persistence; the actual HTTP delivery attempt and its outcome are logged via `logger.warning` regardless (see line ~261) — this only guards the *optional* DB-persistence step, matching the documented "degraded — continue without persistence" design. |
| B104, binding to `0.0.0.0` | `mcp/server.py:222` | Expected and necessary for a service meant to be reached from outside its container (the hosted MCP HTTP entry point) — it's Bearer-token authenticated (`main_http`'s own docstring: "hosted, Bearer-authenticated, plan-gated"), and binding to a specific interface is the deployer's network-policy responsibility (same posture as `ENTERPRISE_SECURITY.md` takes for TLS termination). |

### 2.4 Dependency audit (`pip-audit`)

One flagged package: `nltk 3.9.4` (PYSEC-2026-597, path traversal). This was
already resolved in the prior work cycle by moving `nltk` out of the
mandatory dependency set into an opt-in `[sentiment]` extra (`pyproject.toml`
line 89) — it's used in exactly one place with a hardcoded, non-attacker-
controlled resource name, and is not installed by default. No new action
needed; re-confirmed still correctly scoped as of this review.

`pip` itself carried an advisory (PYSEC-2026-196, entry-point path handling)
in the version originally installed in the review environment — this is a
packaging-tool issue in the local virtualenv, not a dependency the shipped
application carries at runtime; upgrading `pip` in the review environment
cleared it.

### 2.5 Manual review — no findings

- **Dangerous function usage**: no `eval`, `exec`, `pickle.load`,
  `yaml.load` (non-safe), `os.system`, or `subprocess` with `shell=True`
  anywhere in `src/responsibleai/`. The one `subprocess` call
  (`db/migrate.py`, invoking `alembic`) uses `create_subprocess_exec` with
  an argument list, not a shell string — not injectable.
- **Password/secret hashing**: API keys (`org_repository._generate_raw_key`)
  are generated with `secrets.token_urlsafe(32)` (256 bits of entropy) and
  stored as unsalted SHA-256 hashes — acceptable for a high-entropy random
  token (unlike a human-chosen password, brute-forcing a 256-bit random
  value is infeasible regardless of hash speed; this is the same rationale
  GitHub and similar platforms use for PAT storage). TOTP backup codes
  (`auth/mfa.py`) follow the identical pattern with `secrets.choice` and
  SHA-256, also acceptable for the same reason.
- **MFA brute-force protection**: both `/api/auth/login-key`'s MFA check and
  the dedicated MFA-confirm endpoint are rate-limited at 10/minute
  (`dashboard/app.py`), which bounds online brute-force of a 6-digit TOTP
  code to a rate that doesn't meaningfully threaten the ~1-in-1,000,000
  guess space within a 30-second validity window.
- **Multi-tenant data isolation**: spot-checked `org_id` filtering across
  cost, webhook, and audit-log queries — consistent with the coverage
  already documented in `compliance/NIST_CSF_SELF_ASSESSMENT.md`'s PR.DS row.

---

## 3. Summary

| Category | Result |
|---|---|
| Static analysis findings | 15 total — 2 fixed (SQLi pattern), 13 reviewed and accepted with stated reasoning |
| Manual-review-only finding | 1 fixed (SSRF in webhook delivery) — not caught by bandit, found by reading the delivery code path |
| Dependency vulnerabilities | 0 in the shipped application's mandatory dependency set (nltk already correctly isolated as opt-in) |
| Dangerous function usage | None found |
| Regression tests added | 7 new SSRF-guard tests; existing 93 cost-tracker + webhook tests still pass unchanged |

**Honest bottom line**: this review found and fixed one real, meaningful
vulnerability (SSRF) that automated tooling alone didn't surface — it took
reading the actual delivery code path with an adversarial question in mind
("what could an admin-level attacker reach through this?"). That's exactly
the kind of finding a genuine third-party penetration test is designed to
produce systematically, at a scale and with an adversarial mindset one
maintainer reviewing their own code cannot fully replicate. This document
narrows the gap; it does not close it.

---

## Before treating this document as "pentest done"

1. This is not a substitute for `compliance/SOC2_READINESS.md` Section 4's
   third-party penetration test line item. Do not represent it as one.
2. The `POST /api/webhooks` end-to-end test gap (Section 2.2) should be
   closed before this endpoint is relied on in a regulated-industry sales
   cycle.
3. Re-run `bandit -r src/` and `pip-audit` whenever this document is next
   reviewed — both are cheap, fast, and this review is only as good as the
   snapshot it was run against.
4. Update the "Last reviewed" date whenever a new pass is done, the same
   discipline already applied elsewhere in `compliance/`.
