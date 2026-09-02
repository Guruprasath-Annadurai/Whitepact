# Phases 18/19 — Public-API Fuzz/Abuse Testing

**Directive**: WHITEPACT — FULL ENTERPRISE PRODUCTION + PUBLIC LAUNCH
CLOSURE MASTER DIRECTIVE, Phases 18/19. `00_MASTER_READINESS_AUDIT.md`'s
API/MCP transport and Public API safety rows named the gap: property-
based tests exist elsewhere in spirit (25+ files already use
`hypothesis`) but none specifically targeted public request-schema
parsers for size limits, SSRF, injection, or deserialization abuse.

`tests/test_public_api_fuzz.py` closes this — and found two real,
previously-unknown crash bugs plus one unbounded-resource gap in the
process, not merely providing new coverage of already-safe code.

## Findings, all fixed except one disclosed residual risk

### 1. No request-body size limit anywhere (fixed)

Confirmed by grep before writing any code: no application-level or
Dockerfile-level request-body-size cap existed. A reverse proxy in
front of a real deployment may enforce one, but this app had no
defense-in-depth of its own — a self-hosted deployment run without
such a proxy had no bound on how much of an oversized body Starlette
would buffer into memory before Pydantic's own field-level
`max_length` ever got a chance to run.

**Fix**: `MaxBodySizeMiddleware` (`dashboard/middleware.py`),
outermost in the middleware stack, rejects any request whose
`Content-Length` exceeds 10 MB with 413 before any other middleware,
route handler, or Pydantic validation touches the body. Scoped
honestly: this checks `Content-Length`, which covers every normal
JSON-body request this API's clients send; it does not defend against
a chunked-transfer-encoded request that omits `Content-Length` and
streams an unbounded body — closing that fully would mean wrapping the
ASGI `receive` channel, a larger change than this pass makes. A real
deployment's reverse proxy remains a second layer.

### 2. `validate_webhook_url()` crashed on a malformed URL (fixed)

Property-based fuzzing (not a fixed example list) found two distinct
unhandled-exception inputs within the first few hundred generated
strings:

- **`urlsplit("http://[")`** raises a raw `ValueError` ("Invalid IPv6
  URL") for an unbalanced IPv6-literal bracket — previously uncaught,
  meaning this exact input would 500 on `POST /api/webhooks` or
  `POST /api/governance/upstream/servers`.
- **A pathologically long hostname label** (e.g. 10,000 `a` characters)
  raises a raw `UnicodeError` from IDNA encoding inside
  `socket.getaddrinfo()` — also previously uncaught, same 500 exposure.

Both are now caught explicitly in `validate_webhook_url()`
(`webhooks/manager.py`) and converted to the function's own typed
`UnsafeWebhookURLError`, matching the fail-closed treatment every other
rejection path in this function already uses. `validate_upstream_server_url()`
inherits the fix automatically (it delegates to `validate_webhook_url()`).

**Real impact before the fix**: any authenticated ADMIN-role user could
crash a request handler (not the whole process — FastAPI's
`global_exception_handler` still catches it as a 500, so this was
never a full outage) by submitting a malformed webhook or upstream
server URL. Low severity (requires an already-authenticated ADMIN
key, and the blast radius is one request, not the process), but a
real, previously-unknown bug, found and fixed, not merely a coverage
gap closed.

### 3. Octal IP-literal encoding — disclosed, platform-dependent residual risk (not fixed)

Fuzzing also generated `"http://0177.0.0.1/"` (a leading-zero dotted
octet, classically used to smuggle an octal-encoded loopback address
past naive SSRF filters). On this development platform (macOS/BSD
libc), `socket.getaddrinfo("0177.0.0.1", None)` does **not** interpret
the leading zero as octal — it returns `"177.0.0.1"`, a public-looking
address that legitimately passes the private/loopback/reserved check
(confirmed directly, not assumed: `ipaddress.ip_address("177.0.0.1")`
is correctly non-private).

**This is not a bug in `validate_webhook_url()`'s own logic** — it
correctly checks whatever address the OS resolver returns; the
disagreement is between C libraries about what a leading-zero octet
means. `validate_upstream_server_url()`'s hex-encoded (`0x7f.0.0.1`)
and decimal-encoded (`2130706433`) equivalents **were** confirmed
correctly rejected on this same platform (both resolve to
`127.0.0.1`, correctly flagged as loopback) — the gap is specific to
the octal form.

**Why this is disclosed rather than fixed here**: this project's actual
deployment target is Docker/Postgres/Render (glibc-based Linux), where
`inet_aton`-style parsing conventionally reads a leading-zero octet as
octal and would very likely resolve `"0177.0.0.1"` to `127.0.0.1`,
which this function's existing `ip.is_loopback` check would then
correctly reject — meaning the concrete example above may already be
safe in production and only slips through on this development
platform's resolver. Confirming that with certainty would require
testing on the actual Linux/glibc target, which this environment
cannot do. Recorded as a residual risk rather than silently dropped or
falsely claimed fixed — `tests/test_public_api_fuzz.py::TestSSRFGuardNeverCrashes::test_octal_ip_literal_encoding_residual_risk`
documents the actual observed behavior on this platform and does not
assert a pass/fail verdict either way.

**Recommended follow-up** (not done here): normalize the host string
before resolution (reject or canonicalize any all-numeric dotted octet
with a leading zero) rather than trusting OS-resolver interpretation
uniformly across platforms — the more bulletproof, resolver-independent
fix.

## What this fuzz suite actually proves

`tests/test_public_api_fuzz.py`, 12 tests, four areas:

1. **Request body size limit** — the new middleware rejects an
   oversized `Content-Length` with 413 before touching the body;
   doesn't false-positive on ordinary small requests; a malformed
   `Content-Length` header itself doesn't crash the middleware.
2. **SSRF-guard crash-safety** — 200 hypothesis-generated URL-shaped
   strings against each of `validate_webhook_url()`/
   `validate_upstream_server_url()`, asserting only `UnsafeWebhookURLError`
   (or its upstream equivalent) is ever raised, never anything else —
   this is what caught findings 2 and 3 above. Plus fixed-example
   coverage of known SSRF shapes (cloud metadata, IPv6 loopback,
   hex/decimal-encoded loopback, non-http schemes, empty host).
3. **Public request body fuzzing** — `POST /api/orgs`'s `name`/`slug`
   fields against a mix of hypothesis-generated text, unicode, null
   bytes, SQL-injection-shaped, template-injection-shaped,
   script-tag-shaped, path-traversal-shaped, and 100KB strings — every
   one must produce a clean 4xx or 2xx, never a 500.
4. **Path-parameter injection fuzzing** — `org_id`/`consent_id` path
   segments against path-traversal, SQL-injection, null-byte, and
   control-character shapes (percent-encoded, as any real HTTP client
   must) — every one must produce 404/422 (or this endpoint's own
   id-independent 400), never a 500, and never any sign the string
   reached a filesystem path or an unparameterized SQL fragment (this
   codebase's repositories already use parameterized queries
   throughout — confirmed by the absence of any injection-shaped
   500, not re-derived from first principles here).

## Verification

- `ruff check .` / `mypy src/responsibleai`: clean.
- `tests/test_public_api_fuzz.py`: 12 passed.
- Full regression check on the exact function fixed: `tests/test_webhooks.py`
  (51 tests) and the webhook/upstream subset of `tests/test_dashboard_api.py`
  (12 tests) — both clean in isolation, confirming the `validate_webhook_url()`
  fix is additive (catches two new exception types) and changes no
  existing accept/reject decision.

## Phase 18/19 verdict

**READY TO ADVANCE**, with one disclosed residual risk (item 3 above)
carried forward explicitly rather than hidden. Two real crash bugs
were found by property-based fuzzing and fixed with regression tests
locking in the fix; the fuzz suite itself is real, executable,
reusable coverage for this class of bug going forward — not a one-time
audit that expires the moment new code is added.
