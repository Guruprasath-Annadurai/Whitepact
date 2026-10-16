# Connecting an AI assistant to hosted WhitePact — what is supported, what is not (preparation)

Nothing here is a launch statement. There is **no qualified public endpoint** yet (`MCP_HOSTNAME_RUNBOOK.md`) and no
real assistant has ever completed a connection. This page says what the code is designed to support, what is blocked,
and how a genuine compatibility test will be run once a staging endpoint and test access exist.

## Support matrix (code-level, not demonstrated against the vendors' real clients)
| Assistant | Transport | Auth | Redirect/callback | Status |
|---|---|---|---|---|
| ChatGPT (custom connector / app) | Streamable HTTP `/mcp` | OAuth 2.1, PKCE S256, DCR | documented ChatGPT callbacks allow-listed | **expected to work; never tested live** |
| Claude (claude.ai, Desktop, mobile, Cowork) | Streamable HTTP `/mcp` | OAuth 2.1, PKCE S256, DCR | `https://claude.ai/api/mcp/auth_callback` allow-listed (REC-40) | **expected to work; never tested live** |
| Claude Code | Streamable HTTP | OAuth with loopback redirect | **not accepted** (deliberate) | unsupported; use a static reviewer key if a test is needed |
| Grok custom connector | Streamable HTTP | unknown | **no callback known or allowed** | unsupported until the vendor's value is verified |
| Any MCP client with a static key | Streamable HTTP / SSE | Bearer API key | n/a | works (tested in-process) |
| Local stdio | stdio | none | n/a | **advisory only** — no enforcement; documented in `LOCAL_STDIO_MCP_SCOPE.md` |

Hosted tool calls are governed (purpose required, policy, approvals, evidence). The four read-only authority tools are
**development-only** and appear only when the deployment provides a dedicated read-only database role.

## What an operator must provide
`WHITEPACT_MCP_OAUTH_ISSUER`, `WHITEPACT_MCP_OAUTH_RESOURCE_URI` (exactly the URL a user types into the assistant, path
included), `RAI_MCP_HTTP_ALLOWED_HOSTS`/`_ORIGINS`, an organization-scoped credential per reviewer, and — for the authority
tools — `WHITEPACT_AUTHORITY_READ_DATABASE_URL`.

## How a genuine live test will be run (needs a staging endpoint + test access; none exists)
1. Provision a disposable reviewer tenant (`DIRECTORY_REQUIREMENTS_AND_REVIEWER_TENANT.md`, section 2) — founder go required.
2. Run the vendor-neutral conformance checker from a clean machine:
   `WHITEPACT_COMPAT_TOKEN=<reviewer token> python scripts/live_mcp_compat_check.py --base-url https://<staging> --resource https://<staging>/mcp`
   It checks the 401 challenge, protected-resource and authorization-server metadata, PKCE S256, tool listing and annotations
   and one read-only authority call; it never prints the token, never registers clients, never calls a state-changing
   tool, and exits non-zero on any failure **or skip**.
3. In each assistant, add the staging URL as a **custom connector** (Claude supports this on all plans; ChatGPT developer
   mode; Grok connectors page), complete OAuth with the reviewer account, and run the three example prompts. Record
   screenshots/transcripts in the issue register with date, client version and result — including failures.
4. Only then update `WHITEPACT_AI_ASSISTANT_COMPATIBILITY_MATRIX.md` from "expected" to "demonstrated" per client.

## Developer / reviewer accounts
Procedure and requirements: `DIRECTORY_REQUIREMENTS_AND_REVIEWER_TENANT.md`. No account, credential or tenant has been
created. Credentials never go in Git, docs, issues or PRs.

## Blockers (all infrastructure or founder decisions)
Endpoint on an owned domain; TLS/DNS; reviewer tenant provisioning; vendor developer accounts and verification;
Anthropic egress range reachability (`160.79.104.0/21`) through any WAF; real clients' version-specific behaviour.
