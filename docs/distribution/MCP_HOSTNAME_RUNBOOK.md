# `mcp.whitepact.com` — canonical MCP endpoint runbook (PREPARATION ONLY)

Founder decision 1: the canonical hostname is `mcp.whitepact.com`.
**Not authorized and not done:** any live DNS change, migrating the hosted service, deploying
production infrastructure, or promoting the existing hosted service to an official production
endpoint. Every step below that changes the outside world is marked **[FOUNDER GO]** and must not be
run without an explicit written go from the founder for that step.

## 0. Current state (verified in this repository)

| Capability | State | Evidence |
|---|---|---|
| HTTPS-only OAuth issuer and resource | **Enforced**: the OAuth server refuses a non-`https://` issuer or resource at construction. | `auth/mcp_oauth.py` |
| Protected-resource metadata (RFC 9728) | **Served** at `/.well-known/oauth-protected-resource`; lists the issuer as authorization server. | `mcp/server.py` |
| Authorization-server metadata (RFC 8414) | **Served** at `/.well-known/oauth-authorization-server`. | same |
| PKCE S256, rotating refresh tokens | **Implemented**. | `auth/mcp_oauth.py` |
| Exact-match redirect URIs, no open redirect | **Implemented**: a redirect URI must exactly match one registered for the client; authorize errors redirect only to a registered URI. | `auth/mcp_oauth.py:193` |
| **Dynamic client registration accepts only ChatGPT redirect URIs** | **Blocker for other assistants.** Claude and Grok callbacks are rejected (`invalid_redirect_uri`), so OAuth cannot complete from them today. A code change plus Antigravity review is required before testing either. Do not loosen to a wildcard. | `_valid_chatgpt_redirect` |
| Health / readiness | `/health` (liveness) and `/ready` (database ping, 503 when down). | `mcp/server.py` |
| DNS-rebinding protection | Opt-in: set `RAI_MCP_HTTP_ALLOWED_HOSTS=mcp.whitepact.com` and `RAI_MCP_HTTP_ALLOWED_ORIGINS`. **Must be set in production**; unset means unprotected. | `mcp/server.py` |
| Tenant-aware auth | Org is resolved from the verified credential on every request. | tests `test_transport_credential_negatives.py`, `test_mcp_authority_tools.py` |
| Domain-ownership challenge for OpenAI | `/.well-known/openai-apps-challenge` returns the token from `openai_apps_challenge_token` (404 when unset). Token is issued by OpenAI during verification — founder action. | `mcp/server.py` |
| Existing hosted service | **Not qualified.** It runs an older build, is not on the owned domain, and must not be described as the official endpoint. | `docs/distribution/WHITEPACT_GLOBAL_DISTRIBUTION_READINESS_REPORT.md` |

## 1. Required configuration (names verified in code)

```
WHITEPACT_ENV=production                         # unified production detection; conflicts => production
WHITEPACT_MCP_OAUTH_ISSUER=https://mcp.whitepact.com
WHITEPACT_MCP_OAUTH_RESOURCE_URI=https://mcp.whitepact.com/mcp
RAI_MCP_HTTP_ALLOWED_HOSTS=mcp.whitepact.com
RAI_MCP_HTTP_ALLOWED_ORIGINS=https://mcp.whitepact.com
# DB URL, identity webhook secret (>=32 chars), witness/key material: from the secret manager,
# never from this repository or a shell history.
```

Production preflight (`enterprise/preflight.py`) refuses start-up with static `RAI_API_KEYS`, disabled
auth, or a weak identity webhook secret; settings refuse unsafe flags in production.

## 2. Domain ownership and TLS

1. **[FOUNDER]** Confirm the founder controls `whitepact.com` at the registrar and that the registrar
   account has MFA enabled and a recovery path that is not a single mailbox.
2. Prefer a CAA record limiting issuance to the chosen CA (`0 issue "<ca>"`), and DNSSEC if the
   registrar supports it. **[FOUNDER GO]** to publish.
3. TLS terminates at the platform load balancer with TLS 1.2+ (1.3 preferred), HSTS
   (`max-age>=31536000`), a certificate for exactly `mcp.whitepact.com` (no wildcard needed), and
   automatic renewal with an expiry alert at 21 days.
4. Do not point the apex or `www` (website — Codex-owned) at the MCP service. The MCP host is its own
   record so the website and the service can be changed and rolled back independently.

## 3. Environments (separation is a requirement, not a nicety)

| | Staging | Production |
|---|---|---|
| Hostname | `mcp-staging.whitepact.com` | `mcp.whitepact.com` |
| OAuth issuer / resource | its own, never shared | its own |
| Database / Redis / secrets | separate instances and credentials | separate |
| Tenants | disposable reviewer tenants only (see the reviewer procedure) | real customers |
| Tokens | not valid in the other environment (different issuer ⇒ audience mismatch) | |

A token minted by staging must be rejected by production; test that before go-live.

## 4. DNS and deployment steps (all **[FOUNDER GO]**; do not run now)

1. Deploy the qualified build to **staging** from an attested release artifact; verify the build
   provenance attestation before deploying (`gh attestation verify`).
2. Create `mcp-staging` DNS record → staging load balancer. Run the acceptance list in section 5.
3. After Antigravity sign-off and founder go: create `mcp` DNS record (CNAME/ALIAS to the platform
   endpoint) with a **low TTL (300 s)** for the first 48 hours.
4. Smoke test (section 5) against production with a disposable reviewer tenant.
5. Raise TTL to 3600 s after 48 hours of clean operation.

Rollback: remove or repoint the `mcp` record (TTL 300 s ⇒ ≤ 5 minutes to take effect); revoke
issued OAuth clients/tokens by rotating the OAuth signing configuration; no data migration is
involved in the DNS step itself.

## 5. Acceptance checks (run per environment)

- `GET /health` 200; `GET /ready` 200 with DB up and 503 with DB down.
- `GET /.well-known/oauth-protected-resource` → `resource` equals the configured resource URI;
  `authorization_servers` equals the issuer; both `https`.
- `GET /.well-known/oauth-authorization-server` → every endpoint is under the issuer origin.
- Registration with a non-allow-listed redirect URI → `invalid_redirect_uri`; authorize with an
  unregistered `redirect_uri` → error page, **no redirect**.
- PKCE required: authorize without `code_challenge` fails; `plain` method refused.
- Request with `Host: evil.example` → rejected (rebinding protection on).
- A token for tenant A cannot read tenant B (re-run `test_mcp_authority_tools.py` semantics against
  the environment with two disposable tenants).
- Unauthenticated `/mcp` → 401 with a `WWW-Authenticate` pointing at the protected-resource metadata.

## 6. Open items before this can be executed

1. Decide the CA/CAA policy and DNSSEC (founder).
2. Provision the platform, load balancer, database, Redis, secret store (infrastructure owner;
   spending — not authorized).
3. Extend dynamic registration to the documented Claude and Grok callbacks **only after** verifying the
   exact values from each vendor's current documentation, with exact-match rules and tests, and an
   Antigravity review. Until then those assistants are *not* expected to work.
4. Implement the production read-only database role for the authority tools
   (`docs/launch/AUTHORITY_READ_PATH.md`).
5. Real-assistant compatibility tests need a staging endpoint on this hostname and test access.
