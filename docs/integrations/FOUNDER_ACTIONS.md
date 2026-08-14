# Founder actions — multi-platform MCP onboarding

Everything below requires the founder personally: an account, a legal
identity, a payment, or a UI confirmation Claude cannot provide. Grouped
by what kind of action is needed, per the task brief. This is scoped to
the platform-onboarding work in `docs/integrations/`; the pre-existing,
broader list (OpenAI submission, MCP registry, compliance items) is
still in `FOUNDER_ACTION_CHECKLIST.md` and not duplicated here.

## READY NOW (zero-cost, no account needed)

| Platform | Action | Why Claude can't do it | Evidence prepared | Next step |
|---|---|---|---|---|
| Cursor | Copy `.cursor-example/mcp.json` into your own `~/.cursor/mcp.json` | Requires your own local Cursor install | Config file, docs | Copy, paste your API key, reload Cursor |
| Amazon Q | Add `examples/amazon-q/mcp-config.json` to your Amazon Q config | Requires your own local Amazon Q install | Config file, docs | Copy config, confirm config path for your version |

## API KEY REQUIRED

| Platform | Action | Why Claude can't do it | Evidence prepared | Next step |
|---|---|---|---|---|
| xAI Grok | Run `examples/grok/remote_mcp_example.py` for real | **Run live 2026-08-14** with real keys — blocked by a `403 permission-denied`: "team has either used all available credits or reached its monthly spending limit," even after a $5 credit purchase on console.x.ai | Working example script; live error confirms auth/schema reach the API correctly, blocked purely on account credits | Check console.x.ai billing page directly to confirm the $5 credit actually applied; may need to wait for it to process or raise the spending limit |
| Gemini | Run `examples/gemini/remote_mcp_example.py` for real | **Run live 2026-08-14** with real keys — found and fixed two real bugs in the process (wrong API method `models.generate_content` vs `interactions.create`; a model name deprecated for new users despite still appearing in the SDK's own type hints). After fixing both, tool-config schema is now confirmed accepted by the live server; blocked by a `429` requiring a billing-enabled Google Cloud project | Corrected, live-schema-verified example script | Enable billing on the Google Cloud project behind `GEMINI_API_KEY` |

## UI CONFIRMATION REQUIRED

| Platform | Action | Why Claude can't do it | Evidence prepared | Next step |
|---|---|---|---|---|
| Claude | Add WhitePact as a custom connector via Settings → Connectors | Needs an interactive Claude session with your own account | Exact click-path in `claude.md` | Follow the steps, confirm 27 tools appear |
| GitHub Copilot | Run `copilot mcp add ...` and confirm tool discovery | Copilot CLI not installed in this environment | Exact command in `github-copilot.md` | Install Copilot CLI, run the command |
| Microsoft Copilot Studio (Mode 1) | Add WhitePact as a custom connector in your tenant | No live Copilot Studio tenant available | Endpoint/auth documented in `microsoft-copilot.md` | Add connector via Copilot Studio admin UI |
| xAI Grok (connector path) | Add WhitePact in `grok.com/connectors` | Needs your own grok.com session | Click-path in `grok.md` | Add custom connector, paste API key |
| AWS AgentCore | Register WhitePact as a Gateway target | No AgentCore Gateway instance available | Example target config in `examples/aws-agentcore/` | Provision Gateway, register target |

## ACCOUNT REQUIRED

| Platform | Action | Why Claude can't do it | Evidence prepared | Next step |
|---|---|---|---|---|
| Amazon Q | Install/sign in to Amazon Q Developer tooling | No account access | Config prepared | Install, sign in, add config |
| AWS AgentCore | AWS account with Bedrock AgentCore access | No account access | Reference architecture + example config | Provision account/access |

## LEGAL ENTITY REQUIRED

| Platform | Action | Why Claude can't do it | Evidence prepared | Next step |
|---|---|---|---|---|
| Microsoft Copilot (Mode 2, certified) | Partner Center publisher/business verification | Requires a real registered business entity; Radtech LLP is not yet incorporated (see `distribution/microsoft/FOUNDER_SUBMISSION_CHECKLIST.md`) | Full checklist prepared | Incorporate or verify as individual publisher, then create Partner Center account |

## DOMAIN REQUIRED (soft — current URLs work, but aren't branded)

| Platform | Action | Why Claude can't do it | Evidence prepared | Next step |
|---|---|---|---|---|
| Microsoft Copilot (Mode 2) | Decide whether a `whitepact.<tld>` domain is needed before submission, or whether the current raw-GitHub privacy/terms URLs are acceptable | Domain purchase/DNS is an explicitly excluded action | Verified-live raw-GitHub URLs as a working interim | Decide, then purchase/point a domain if wanted |

## SUBMISSION REQUIRED

| Platform | Action | Why Claude can't do it | Evidence prepared | Next step |
|---|---|---|---|---|
| Microsoft Copilot (Mode 2) | Submit the certified connector application | Marketplace submissions are explicitly excluded | `distribution/microsoft/` package | Complete checklist items 1-5 first |
| GitHub curated registry | Outreach to get WhitePact into GitHub's curated Copilot registry (separate from the open MCP Registry, where it's already live) | Requires a real outreach relationship | Live MCP Registry listing as supporting evidence | Decide whether to pursue; no outreach sent |

## BLOCKED

| Platform | Action | Why Claude can't do it | Evidence prepared | Next step |
|---|---|---|---|---|
| Mistral Le Chat | Confirm the real, official MCP Connectors submission channel | No confirmed official channel found in research — only an unofficial community repo | `docs/adr/ADR-MISTRAL-MCP-TRANSPORT.md` documents exactly what was and wasn't confirmed | Contact Mistral directly (dev relations, official docs, or your own account) rather than treat the unofficial repo as authoritative |
