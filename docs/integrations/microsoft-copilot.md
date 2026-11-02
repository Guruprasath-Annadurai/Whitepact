# Microsoft Copilot / Copilot Studio

**Status**: CONFIG_READY (technical prep only — submission is a founder
action). See `PLATFORM_COMPATIBILITY.md`.
**Source-of-truth date**: 2026-08-13.

Two distinct integration modes exist for Microsoft's ecosystem:

## Mode 1 — Copilot Studio custom connector (works today, no submission)

A Copilot Studio admin can add WhitePact as a custom connector pointing
at the Streamable HTTP endpoint directly — no Microsoft review process is
required for this mode, it's tenant-admin bring-your-own, same pattern as
Microsoft's own MCP docs describe.

- Endpoint: `https://whitepact-mcp-http.onrender.com/mcp`
- Auth: Bearer API key, configured as the connector's outbound auth
- Setup: Copilot Studio → Custom connectors → add MCP server URL +
  header. Exact menu path depends on the admin's tenant configuration
  and was not exercised here — no live Copilot Studio tenant available.

This mode reaches CONFIG_READY the same way every other platform in this
set does; it needs a Microsoft 365 tenant with Copilot Studio access to
actually verify, which Claude does not have.

## Mode 2 — Microsoft-certified connector (requires submission)

This is the path that needs Partner Center, business verification, and a
real review cycle. **Not attempted** — see
`distribution/microsoft/FOUNDER_SUBMISSION_CHECKLIST.md` for exactly
what's prepared vs. what still needs the founder.

Preparation artifacts live in `distribution/microsoft/` (OpenAPI-style
metadata, tool documentation, auth documentation, icon references,
placeholders explicitly marked where a legal URL doesn't exist yet).

## Safe test prompt (Mode 1)

> "Use whitepact's rai_iso42001_gap tool to check this control statement:
> 'We do not maintain an AI risk register.'"

## Security notes

Same as every other platform: Bearer-key auth, read-only tools, no
platform-specific override of WhitePact's DENY/ALLOW logic.

## Founder actions

- Mode 1: verify the custom-connector setup against a real Copilot Studio
  tenant.
- Mode 2: everything in
  `distribution/microsoft/FOUNDER_SUBMISSION_CHECKLIST.md` — Partner
  Center account, publisher/business verification, actual submission.
