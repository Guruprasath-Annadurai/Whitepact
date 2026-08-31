# WhitePact — Anthropic Connectors Directory submission package

Date: 2026-08-31

This package is prepared against Anthropic's current public submission documentation for remote MCP connectors. It is a submission-readiness artifact, not evidence of acceptance, endorsement, partnership, or directory publication.

## Current submission route

Anthropic's current Connectors Directory documentation says remote MCP submissions happen inside Claude.ai's submission portal in an organization's admin settings. The submitter needs a Team or Enterprise organization and directory-management access. On Team, this is limited to Owners/Primary Owners; Enterprise can delegate the Directory or Libraries permission through custom roles.

WhitePact is a remote MCP server, so it belongs in the remote-MCP submission path, not the desktop-extension/MCPB form.

## Canonical WhitePact metadata

- Name: WhitePact
- Type: Remote MCP server
- Repository: https://github.com/Guruprasath-Annadurai/Whitepact
- License: MIT
- MCP server identity: `whitepact`
- Hosted endpoint: `https://whitepact-mcp-http.onrender.com/mcp`
- Transport: Streamable HTTP
- Legacy hosted transport: SSE retained for older clients
- Current verified capability count: **30 tools / 20 resources**
- Official MCP Registry namespace: `io.github.Guruprasath-Annadurai/whitepact`
- Current project release line in repository metadata: v1.2.6

## Suggested directory listing copy

### Server name

WhitePact

### Tagline

Runtime governance and trust controls for AI agents

The tagline is under Anthropic's current 55-character maximum.

### Description

WhitePact is an open-source runtime governance and assurance layer for autonomous AI systems. Its remote MCP server exposes 30 governance tools for PII and harmful-content scanning, trust scoring, hallucination and bias evaluation, compliance analysis, red-team checks, cost and drift analysis, and agent-authority controls. WhitePact's governance core uses deterministic five-way decisions — ALLOW, ALLOW_WITH_REDACTION, REQUIRE_APPROVAL, DENY, and QUARANTINE — rather than an LLM-based decision path. The project is MIT-licensed and can also be self-hosted over stdio.

This copy deliberately does not claim enterprise adoption, certification beyond officially awarded public statuses, vendor endorsement, partnership, or third-party production deployment.

## Categories

Use the closest available current categories, preferably:

- Code
- Data
- Productivity

Do not choose a category merely for visibility if it does not accurately describe WhitePact.

## Documentation and support

- Documentation URL: repository README / integration documentation in the official GitHub repository
- Support route: public GitHub Issues for non-security questions
- Security reports: use the private reporting route documented in `SECURITY.md`; do not direct vulnerability reports to public issues

## Anthropic requirements cross-check

Anthropic currently requires submitted MCP connectors to meet these minimums:

1. Security requirements.
2. Every tool must include a `title` plus applicable `readOnlyHint` or `destructiveHint` annotations.
3. Authenticated services must use a supported OAuth 2.0 authentication path.
4. Clear documentation and setup instructions.
5. Accurate privacy-policy information.

WhitePact's repository already contains explicit title/read-only/destructive annotations for the MCP tools and documentation for the hosted endpoint. However, authentication must be treated carefully during submission: a static Bearer API-key deployment is not the same thing as satisfying Anthropic's OAuth requirement. Do not represent static Bearer-key authentication as OAuth.

## Authentication gate — must be verified before submission

The submission portal asks how users authenticate and supports OAuth-based patterns, custom connection, or no authentication depending on the connector design. WhitePact's hosted MCP deployment has historically used static Bearer API keys, while repository code also contains OIDC/OAuth resource-server support when appropriately configured.

Before pressing Submit, verify the actual production endpoint configuration, not only repository capability:

- whether `/.well-known/oauth-protected-resource` is live and correct;
- whether the production issuer/client/JWKS configuration is active;
- whether a reviewer can complete the supported authentication flow end-to-end;
- whether the selected portal authentication mode exactly matches production behavior.

If production OAuth is not configured, do not select OAuth merely because the codebase supports it.

## Tool verification gate

Anthropic says the portal synchronizes the server's tools/prompts/resources and flags missing titles/annotations. Before final submission:

- connect the production Streamable HTTP endpoint;
- confirm **30 tools / 20 resources** are discovered;
- confirm every tool has the expected title and read/write annotations;
- run every submitted tool path that will be relied on during review, using MCP Inspector or Claude custom connector testing;
- record any plan-gated tools accurately rather than implying all tools are available on every plan.

## Listing fields to prepare in the portal

Anthropic's current portal asks for:

- server name (100 characters max);
- tagline (55 characters max);
- description (2,000 characters max);
- one to five categories;
- documentation URL;
- privacy-policy URL;
- support contact;
- icon;
- permanent listing slug;
- primary use cases;
- prerequisites such as accounts/plans;
- whether the connector reads, writes, or both;
- company name and website;
- reviewer contact;
- authentication method;
- data-handling declarations;
- reviewer test-account credentials and exact access instructions;
- confirmation that every tool was tested;
- policy acknowledgments.

## Use cases

Suggested accurate use cases:

1. Scan text for PII or harmful content before an agent continues a workflow.
2. Evaluate trust, hallucination, bias, drift, or compliance signals for AI outputs.
3. Apply deterministic runtime-governance checks to proposed autonomous-agent actions.
4. Assess third-party MCP/tool trust and governance posture before use.
5. Produce governance evidence and compliance-oriented analysis for engineering teams.

## Read/write classification

Do not use a blanket marketing statement unless it matches the current production tool annotations and behavior discovered by the portal. The historical WhitePact MCP tool surface has been intentionally read-only/non-destructive at the tool layer; verify the live 30-tool surface again immediately before submission.

## Privacy-policy gate

The directory requires a privacy-policy URL and accurate data-handling answers. A repository draft that explicitly says it is not final should not be presented as stronger legal assurance than it is. Before final submission, use the actual publicly served policy that governs the hosted service and make sure its statements match real collection, storage, retention, subprocessors, and contact practices.

## Assets

Prepare a current WhitePact icon suitable for Anthropic's listing UI. Interactive MCP Apps additionally need 3–5 PNG carousel screenshots of at least 1000 px width; WhitePact should not claim the interactive-app path unless it actually ships the required MCP App UI.

## Founder/account-bound actions

These cannot be completed through the current repository connector and require the authorized Anthropic account:

1. Sign into the Team/Enterprise Claude organization with directory-management permission.
2. Open the remote MCP submission portal from admin settings.
3. Connect the production endpoint and review the synchronized 30-tool surface.
4. Select the authentication mode that matches the live deployment.
5. Supply the final privacy-policy URL, icon, company/reviewer contact, and test credentials.
6. Complete all required policy acknowledgments.
7. Submit for Anthropic review.

## Claim boundary after submission

After the form is submitted, describe status only as **submitted for Anthropic review** until the submissions dashboard or Anthropic correspondence confirms publication. A submission is not an approval, listing, partnership, endorsement, or adoption signal.

Signed-off-by: Guruprasath Annadurai <Guruprasathannadurai.official@gmail.com>
