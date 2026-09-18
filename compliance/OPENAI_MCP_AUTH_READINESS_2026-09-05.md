# OpenAI / ChatGPT MCP authentication readiness — 2026-09-05

## Evidence boundary

This document records repository and production evidence. It is not a
certification, OpenAI partnership claim, or substitute for an actual ChatGPT
connection test. Secret values are intentionally excluded.

## Original 401 root cause

The production `/mcp` resource accepted only a WhitePact `rai_...` API key (or a
deployment-specific external OIDC JWT) and did not advertise a production OAuth
authorization server. ChatGPT cannot attach a custom API key to an authenticated
MCP connection. The public resource returned `401` with “Provide a valid Bearer
API key,” no OAuth `WWW-Authenticate` discovery challenge, and a 404 protected-
resource metadata endpoint. The MCP service itself was healthy when called with
a valid API key; this was an authentication integration gap, not an availability
failure.

## Selected architecture

WhitePact is both the MCP protected resource and a narrow OAuth 2.1 authorization
server for ChatGPT. The flow is authorization code with PKCE S256 and exact
ChatGPT HTTPS redirect validation. Dynamic client registration creates public
clients with token endpoint authentication method `none`. The `resource`
parameter is required and fixed to the production `/mcp` URL. A tenant-bound
VIEWER or ANALYST credential completes interactive authorization; administrative
credentials are rejected.

Issued access and refresh tokens are opaque. Only SHA-256 digests are persisted.
Access tokens last 900 seconds. Refresh tokens last 2,592,000 seconds, rotate on
every use, and revoke the full family on replay. The sole product permission is
`whitepact:review`; `offline_access` requests a refresh token. Every access checks
scope, resource, expiry, revocation, tenant, subject/key status, role, and the
tenant SSO posture. Existing API-key authentication remains a separate
server-to-server path.

## Current official OpenAI references

- [Authentication](https://developers.openai.com/plugins/build/auth): OAuth 2.1,
  protected-resource discovery, authorization-server metadata, PKCE S256,
  resource binding, client registration options, token validation, and runtime
  `WWW-Authenticate` challenges.
- [Connect and test in ChatGPT](https://developers.openai.com/plugins/deploy/connect-chatgpt):
  production HTTPS connection and developer-mode testing workflow.

OpenAI's documentation also states that ChatGPT cannot provide a custom API key
to a remote MCP server. That is why the API key is used only inside WhitePact's
own interactive authorization step and is never ChatGPT's MCP Bearer token.

## Security controls and tests

The focused authorization-server suite currently contains 20 passing tests. It
covers OAuth discovery, fail-closed unauthenticated MCP, PKCE downgrade,
redirect manipulation, wrong resource/audience, admin credential rejection,
malformed Authorization headers, query-string token rejection, short-lived
access, refresh rotation and replay-family revocation, access revocation,
expiry, tenant/subject binding, cross-tenant substitution, client revocation,
one-use authorization codes, invalid/forged tokens, missing scope, credential-
free audit records, 30 tools, 20 resources, and successful execution of all five
OpenAI review tools. Tokens are absent from response bodies, logs, and audit
events in the tested failure paths.

The pending authorization handle and authorization code are both one-use and
stored only by digest. The client `state` is bounded, retained server-side, and
echoed unchanged with the issuer parameter; the high-entropy one-use request
handle protects the authorization form itself. Authentication failures are rate
limited. Every OAuth tool descriptor declares `whitepact:review` in both the
current field and compatibility metadata.

## Production endpoints

- MCP resource: `https://whitepact-mcp-http.onrender.com/mcp`
- Protected-resource metadata:
  `https://whitepact-mcp-http.onrender.com/.well-known/oauth-protected-resource`
- Authorization-server metadata:
  `https://whitepact-mcp-http.onrender.com/.well-known/oauth-authorization-server`
- Authorization endpoint: `https://whitepact-mcp-http.onrender.com/oauth/authorize`
- Token endpoint: `https://whitepact-mcp-http.onrender.com/oauth/token`
- Registration endpoint: `https://whitepact-mcp-http.onrender.com/oauth/register`
- Revocation endpoint: `https://whitepact-mcp-http.onrender.com/oauth/revoke`

## Verification status

Repository implementation and focused local tests: **PASS**.

Production revision `7389772836bfc280b5484075ba64f167dded9fa7` was deployed
through Render deployment `dep-daduvi740ujc73d3hjn0` on 2026-09-05. Public
verification passed for `/health` (30 tools), RFC 9728 protected-resource
metadata, OAuth authorization-server metadata, exact issuer/resource/scope
advertisement, and the unauthenticated MCP failure path. An unauthenticated
`POST /mcp` returns `401` with a `WWW-Authenticate` challenge pointing to the
protected-resource metadata and requesting `whitepact:review`. Render's
`RAI_MCP_HTTP_ALLOW_UNAUTHENTICATED_DEMO` setting was independently checked as
`false`; its value and all other credentials are excluded from this record.

Public OAuth discovery and negative-auth verification: **PASS**.

Production token issuance, refresh, revocation, tenant binding, authenticated
MCP initialization, and tool execution: **PENDING AN AUTHORIZED REVIEWER
CREDENTIAL; LOCAL AUTOMATED COVERAGE PASSES BUT IS NOT PRODUCTION EVIDENCE**.

Actual founder-bound ChatGPT authorization and five-tool execution:
**PENDING; NOT YET A PASS**.

No readiness claim may be made until the exact committed revision is deployed,
public metadata and negative-auth probes pass, and an actual ChatGPT connection
executes WhitePact tools rather than returning a generic model response.
