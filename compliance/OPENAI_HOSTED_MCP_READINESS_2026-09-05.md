# OpenAI Hosted MCP Readiness — 2026-09-05

## Scope and deployment

- Base source SHA: `8f8ef53f0460c99115f5656dfa4d31775bca4d6a`
- Public endpoint: `https://whitepact-mcp-http.onrender.com/mcp`
- Hosting provider/service: Render, `whitepact-mcp-http`
  (`srv-d9ub6pe1egvs739i2aa0`), Oregon
- Runtime: repository Dockerfile; startup command `responsibleai-mcp-http`
- Health path: `/health`
- Relevant configuration names: `RAI_DATABASE_URL`, `RAI_REDIS_URL`,
  `RAI_MCP_HTTP_HOST`, `RAI_MCP_HTTP_PORT`,
  `RAI_MCP_HTTP_ALLOW_UNAUTHENTICATED_DEMO`, and
  `RAI_OPENAI_APPS_CHALLENGE_TOKEN`. No values are recorded here.
- Verified deployment: `dep-dadhdmvqj5pc7393hf2g`, source SHA above,
  status `live`; finished `2026-09-04T19:07:50Z`

## Root cause and fix

Before the fix, DNS resolved and TLS 1.3 negotiation completed with a valid
`onrender.com` certificate, but `/health` returned no bytes before the client
timeout. Render application logs then proved the process was exiting during
ASGI lifespan startup: `_db_engine.init()` raised
`asyncpg.exceptions.InvalidPasswordError: password authentication failed for
user "postgres"`. Render recorded repeated non-zero exit code 3 events. The
MCP service's `RAI_DATABASE_URL` differed from the dashboard service's binding;
the dashboard binding was independently healthy (`/api/health`: HTTP 200,
database `ok`, backend `postgresql`).

The production MCP service's stale database binding was replaced with that
verified healthy binding without printing or storing its value, and current
`main` was deployed through Render. No MCP transport, tool handler, schema, or
authentication bypass was changed. Unauthenticated demo mode remained disabled.

The automated public verifier reproduced the pre-fix failure with no successful
MCP operations and one timeout at 10.08 seconds. After deployment, an unauthenticated initialize
failed closed with HTTP 401 in 0.276 seconds. Authenticated verification used a
VIEWER key created for the existing `OpenAI Reviewer Demo` tenant; the key was
revoked immediately after each run.

## Public protocol evidence

- Protocol: MCP Streamable HTTP over public HTTPS
- HTTPS health: PASS
- Initialize: PASS
- `tools/list`: 30 tools; PASS
- `resources/list`: 20 resources; PASS
- Public server card: `whitepact` version `1.2.6`
- All 30 tools expose explicit `readOnlyHint`, `openWorldHint`, and
  `destructiveHint`: PASS
- Unsupported destructive log deletion exposed: no
- Required real tool calls: 15/15 successful across three consecutive runs
- Total verification operations: 19/19 successful
- Timeouts: 0
- HTTP 5xx responses: 0
- Render error logs after deployment through the verification window: 0

| Tool | Runs | Minimum | Average | Maximum | Validated behavior |
|---|---:|---:|---:|---:|---|
| `rai_health` | 3 | 316.3 ms | 347.0 ms | 385.8 ms | status `ok`, 30 tools |
| `rai_scan` | 3 | 323.9 ms | 364.5 ms | 387.4 ms | PII found; email and phone redacted |
| `rai_trust_score` | 3 | 333.0 ms | 358.8 ms | 404.2 ms | numeric score and risk tier returned |
| `rai_eu_ai_act_classify` | 3 | 385.4 ms | 392.5 ms | 400.1 ms | employment screening classified `HIGH` |
| `rai_hallucination` | 3 | 331.9 ms | 362.5 ms | 397.9 ms | Tuesday/Wednesday contradiction detected |

The calls used the exact review inputs encoded in
`scripts/verify_hosted_mcp_openai.py`, including the actual
`rai_eu_ai_act_classify` schema fields `system_description`,
`deployment_sector=employment`, `affects_natural_persons=true`, and
`is_fully_automated=true`.

## Repository changes

- `scripts/verify_hosted_mcp_openai.py`: public, authenticated, repeated MCP
  review verifier with latency and failure accounting; credentials are accepted
  only through `WHITEPACT_API_KEY` and are never emitted.
- `tests/test_mcp_http_transport.py`: real ASGI/Streamable HTTP regression for
  initialization, descriptors, annotations, and the five review tools.
- `SPEC.md`: records the unchanged tool-only review flow and its operational
  acceptance contract.
- This evidence record.

## Remaining limitations

- Evidence covers three consecutive authenticated runs after one deployment;
  it is not a load, soak, multi-region, or cold-start availability test.
- The production descriptor currently advertises API-key authentication. OAuth
  authorization-server onboarding remains separate from this timeout fix.
- The service is still hosted under a Render `onrender.com` domain and provider
  availability remains outside repository control.
