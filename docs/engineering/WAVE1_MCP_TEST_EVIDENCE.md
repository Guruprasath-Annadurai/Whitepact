# Wave 1 MCP transport compatibility evidence

Base: `f338556baf9984ab485f2d4758179fb87e8baa4d` (preserved draft PR #198).
Branch: `codex/whitepact-wave1-mcp-tests`.
Exclusive ownership: new `tests/test_mcp_wave1_compatibility.py` and this file.
No production, authority, authentication, billing, runtime, or workflow changes.

## Fresh local execution

Python 3.11.15; existing independent `/private/tmp/wp-sdk-live-clean-install`
environment, with `PYTHONPATH=src:.`:

```sh
python -m pytest tests/test_mcp_wave1_compatibility.py \
  tests/test_mcp_protocol_matrix.py tests/test_mcp_enterprise_trust_domain.py \
  tests/test_mcp_http_transport.py -q --no-cov --tb=short
ruff check tests/test_mcp_wave1_compatibility.py
ruff format --check tests/test_mcp_wave1_compatibility.py
git diff --check
```

Result: **42 passed, 0 failed, 0 skipped**, 24.63 seconds; no pytest warning
summary. Ruff checks/format and diff check passed. Five tests are newly added.
Earlier exploratory runs had two and then one test-expectation failures; they
identified actual existing response contracts rather than requiring source fixes.

## Independently exercised surfaces

- Real separate Python process, stdio MCP client: initialize, ping, tools and
  resources discovery, unknown-tool refusal, and stderr community boundary.
- Real enterprise stdio process: exits 2 before writing protocol bytes; no
  community-mode banner.
- Real Uvicorn TCP listener bound to ephemeral `127.0.0.1`: MCP client initialize,
  ping, tools/resources discovery, unknown resource/tool handling, and missing
  governance purpose refusal.
- Malformed JSON and invalid typed tool arguments over real TCP: no dispatch.
  A dispatch spy observes the negative boundary; it does not replace transport.
- Key revoked in the actual fixture repository: subsequent `/mcp` request carrying
  a session identifier and legacy `/sse` GET both return 401 without key reflection.

## Limits and residual observations

Hosted fixtures use isolated in-memory SQLite with explicit seeded root/consent/
delegation. This is real protocol/TCP coverage, **not PostgreSQL durability,
production identity, Linux containment, independent qualification, or external
client-directory certification**. Community stdio remains explicitly ungoverned.

Unknown resources currently return a JSON error document instead of an MCP
exception. Missing purpose returns `structuredContent.error` while `isError` is
false; consumers must not infer execution success from HTTP 200 or that flag alone.
The test explicitly preserves and verifies that error. Resource handling logs an
existing MCP SDK deprecation for returning a string; no warning-summary suppression
was added. Unknown-tool SDK validation warnings remain diagnostic logs.

Legacy `/messages/` without its required session query returns 400; this does not
prove authenticated existing SSE message-session behavior. No claim about that
case is made. Legacy end-to-end SSE, PostgreSQL transport integration, supported
third-party MCP clients, and fresh exact-head GitHub CI remain separate checks.

No credentials are inherited by the stdio subprocess; it runs from pytest's
temporary directory with only explicit development trust-domain/PYTHONPATH inputs.
No deployment, public directory submission, package publication, or security
boundary change occurred. Production remains NO-GO.
