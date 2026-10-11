# Directory submission requirements and the disposable reviewer-tenant procedure (PREPARATION ONLY)

Founder decision 2. Nothing here has been submitted, purchased, registered or provisioned.
**Founder actions** (identity verification, paid-plan activation, accepting vendor terms,
submitting forms) are marked **[FOUNDER]**. No subscription is purchased by engineering.
**No credential, token or reviewer account appears in this repository or any document**; the
procedure below produces them at submission time, outside Git.

Facts about the vendors' processes were read on 2026-10-11 from their public pages and can change;
re-read them on the day of submission.

## 1. Per-platform requirements

### OpenAI (ChatGPT apps / plugin directory)
| Requirement | Owner | Status |
|---|---|---|
| Developer / organization identity verification in the OpenAI portal | **[FOUNDER]** | not started |
| Domain-ownership challenge: `/.well-known/openai-apps-challenge` serves the issued token | Engineering sets `openai_apps_challenge_token` on the verified host after the founder obtains it | endpoint exists; needs `mcp.whitepact.com` (runbook) |
| Public HTTPS MCP endpoint on the owned domain | Founder go required | not deployed |
| OAuth: authorization-code + PKCE; ChatGPT redirect URIs | Implemented; exact ChatGPT callbacks only | ready for ChatGPT only |
| Demo/reviewer account with sample data | Procedure in section 2 | not provisioned |
| Tool annotations (read-only / destructive / open-world) accurate; minimal inputs; no generic executor | Engineering | done for all 30 + 4 tools; Antigravity audit of the 4 authority tools pending |
| Privacy policy and terms URLs | Founder/legal — website is Codex-owned | not confirmed live |
| ZIP/manifest upload in the portal | **[FOUNDER]** to submit | not prepared; do not prepare an official package until the endpoint exists |

### Anthropic (Claude connectors directory)
| Requirement | Owner | Status |
|---|---|---|
| Directory portal access (paid plan needed) | **[FOUNDER]** — no purchase by engineering | not started |
| Privacy policy link; verified contact | Founder | to confirm |
| Standard test account with sample data | Section 2 | not provisioned |
| ≥ 3 realistic example prompts | Engineering (draft below) | drafted |
| Ownership of the endpoint; OAuth 2.0 for authenticated remote MCP | Domain per runbook; OAuth exists | Claude hosted callback now allow-listed (exact match, tested); see the Claude OAuth checklist below |
| Tool names ≤ 64 chars, annotations present | Engineering | done |

Example prompts (read-only, safe against a reviewer tenant):
1. "Summarize my organization's WhitePact policy status and tell me whether its change history verifies."
2. "Would my policy require approval for a `payments.send` action to `vendor-42`? Remember this is only a policy simulation."
3. "List my pending approval requests and tell me which are highest risk."

#### Claude OAuth checklist (Anthropic's connector authentication page, read 2026-10-11)
| Anthropic requirement | WhitePact today |
|---|---|
| `401` (not `200`) with `WWW-Authenticate: Bearer resource_metadata=...` to start sign-in | **Met** (`test_unauthenticated_mcp_is_401_with_oauth_challenge`) |
| Protected-resource `resource` equals the URL users enter, path included; first `authorization_servers` entry is the issuer | **Met by construction**; must be re-checked with the real `https://mcp.whitepact.com/mcp` |
| PKCE S256 on every request; metadata advertises `code_challenge_methods_supported: ["S256"]` | **Met** |
| DCR (`registration_endpoint`) or CIMD | DCR **met**; CIMD not advertised (Claude falls back to DCR). Anthropic notes DCR creates a new client per connection — plan clean-up of stale clients |
| Hosted callback `https://claude.ai/api/mcp/auth_callback` registrable | **Met** (this change) |
| Claude Code loopback redirect (any port, `localhost` and `127.0.0.1`) | **Not supported** (deliberate; needs design + review) |
| Token endpoint accepts `application/x-www-form-urlencoded`; RFC 6749 `invalid_grant`; rotate refresh tokens for public clients; `offline_access` | **Met** (existing OAuth tests) |
| Discovery/registration/token respond within 10 s (refresh 30 s) | Not load-tested over a real network |
| Authorization server reachable from Anthropic's egress range (`160.79.104.0/21`); WAF must not block it | Cannot be checked until an endpoint exists |
| Custom connectors can be added by URL on all Claude plans for testing | Possible once a staging endpoint exists; **no purchase needed**, but still requires an endpoint and test credentials |

### xAI Grok
Grok supports user-added custom MCP connectors by public HTTPS URL; no public third-party
submission programme was found. Therefore: **evaluate by connecting a staging endpoint with test
access, not by submission.** Same OAuth caveat as Claude (callback not allow-listed).

## 2. Disposable reviewer tenant — provisioning procedure (run only on written founder go)

Purpose: give a vendor reviewer a safe, expiring, least-privilege tenant that holds only synthetic data.

**Preconditions:** staging (or production-isolated reviewer environment) exists and passed the runbook
acceptance checks; Antigravity has accepted the authority read path; founder has authorized this
specific submission and named an owner for the credential.

1. **Environment.** Use *staging* (`mcp-staging.whitepact.com`) unless a vendor requires the
   canonical host; never a production customer tenant. If production host is required, use a tenant
   flagged `reviewer`, plan ENTERPRISE (so the 4 tools are entitled), created for that submission only.
2. **Create the tenant** with the organization repository (`OrgRepository.create_org`) named
   `Reviewer – <vendor> – <YYYYMMDD>`. Record its id in the submission ticket, not in Git.
3. **Create principals, least privilege.** One API key / OAuth principal per reviewer, role
   **ANALYST** (policy status, simulation, evidence verification) plus a second **APPROVER** only if the
   vendor asks to view approvals. Never OWNER/ADMIN. Set `expires_at` to **7 days**.
4. **Seed synthetic data only:** a three-rule policy (allow `read.*`, require approval for
   `payments.send`, deny `data.export`), two pending approvals with fictional targets, a short
   evidence chain generated by calling harmless tools. No real customer names, emails or payment data.
5. **Verify before handing over:** run the four authority tools and the sample prompts as the reviewer
   principal; run `tests/test_mcp_authority_tools.py` semantics against the tenant; confirm a second
   disposable tenant cannot be read.
6. **Hand over out-of-band.** Credentials go to the vendor only through the vendor's submission form or
   an encrypted channel the founder chooses. **Never** commit, paste in an issue/PR, or place in docs.
   Reviewer instructions (a one-page, credential-free sheet) may be committed; the secrets may not.
7. **Revoke and delete.** On the expiry date or at vendor sign-off, whichever is first:
   `OrgRepository.revoke_key` for every principal, then `delete_org`; confirm the tenant's tokens fail;
   archive the evidence of provisioning/teardown in the ticket. Record in the register.
8. **Monitoring while live.** Alert on any call from the reviewer principal outside the vendor's stated
   window and on any `role_not_permitted` spike.

Open: a scripted, audited provisioning command does not exist yet; building one is only appropriate once
the staging endpoint exists. Doing the above by hand against a live environment is **not authorized now**.

## 3. Documents the founder must supply or approve
Privacy policy, terms of service, support/security contact, data-processing description, and the
verified legal entity name (the future LLP is not yet incorporated — see project notes; do not name it
as an operator before it exists).
