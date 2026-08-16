# Founder actions — multi-platform MCP onboarding

Everything below requires the founder personally: an account, a legal
identity, a payment, or a UI confirmation Claude cannot provide. Grouped
by what kind of action is needed, per the task brief. This is scoped to
the platform-onboarding work in `docs/integrations/`; the pre-existing,
broader list (OpenAI submission, MCP registry, compliance items) is
still in `FOUNDER_ACTION_CHECKLIST.md` and not duplicated here.

## DONE — xAI Grok (API path)

**Verified live 2026-08-14**, no longer a pending action: full round trip
(connect, auth, tool discovery, tool call, structured response)
succeeded with real credentials. Response was WhitePact's own correct
FREE-plan gating (`hosted_access_unavailable`), not a failure. Two real
bugs found and fixed along the way — see `grok.md` for detail. Only
remaining optional step: upgrade the test org's plan to see a full
data-returning tool response (not required to consider Grok integration
"working").

## DONE — GitHub Copilot CLI

**Verified live 2026-08-15**: installed GitHub Copilot CLI v1.0.80
(`npm install -g @github/copilot`), ran `copilot mcp add` to register
WhitePact, confirmed config with `copilot mcp get whitepact`, and in an
interactive session confirmed a real tool call — `rai_scan` correctly
detected and redacted PII in a test string. Full round trip working; see
`github-copilot.md`. Only remaining GitHub Copilot item is the separate
curated-registry inclusion (see SUBMISSION REQUIRED below), which does
not block this integration.

## DONE — `xai-org/plugin-marketplace` submission

**Submitted 2026-08-14**: PR opened at
[xai-org/plugin-marketplace#244](https://github.com/xai-org/plugin-marketplace/pull/244),
adding WhitePact as a local plugin (`external_plugins/whitepact/`) —
bundles a `.mcp.json` (Streamable HTTP, `WHITEPACT_API_KEY` env var
substitution) and a `SKILL.md` describing when to reach for WhitePact's
tools. Both required local validation scripts passed before submission
(`validate-catalog.py`, `generate-plugin-index.py --check`); all three
of xAI's own automated PR checks (two Socket Security supply-chain
scans, one semgrep scan) confirmed passing shortly after. This makes
WhitePact discoverable to Grok Build (the coding agent)
developers browsing the official plugin marketplace — not `grok.com`
chat users, which still has no public submission path found (see the
`grok.com/connectors` row under SUBMISSION REQUIRED below). Awaiting
xAI code-owner review; nothing further to do until they respond.

## DONE — Cursor

**Verified live 2026-08-15**: added `whitepact` to `~/.cursor/mcp.json`
alongside an existing server, substituted the real API key, restarted
Cursor, and confirmed `whitepact` shows as connected in Cursor's MCP
settings panel. See `cursor.md`.

## READY NOW (zero-cost, no account needed)

| Platform | Action | Why Claude can't do it | Evidence prepared | Next step |
|---|---|---|---|---|
| Kiro CLI | Install (`brew install --cask amazon-q`, the cask that now installs Kiro), sign in, add `examples/kiro-cli/mcp-config.json` to `~/.kiro/settings/mcp.json` | Requires your own local Kiro install | Config file, docs (`kiro-cli.md`) | Install, sign in, copy config, export `WHITEPACT_API_KEY` |

## API KEY REQUIRED

| Platform | Action | Why Claude can't do it | Evidence prepared | Next step |
|---|---|---|---|---|
| Gemini | Run `examples/gemini/remote_mcp_example.py` for real | **Run live 2026-08-14 and 2026-08-15** with real keys — found and fixed two real bugs in the process (wrong API method `models.generate_content` vs `interactions.create`; a model name deprecated for new users despite still appearing in the SDK's own type hints). Cloud billing account linked to the "Default Gemini Project" (`gen-lang-client-0113985869`) 2026-08-15 — this cleared the original `429` free-tier block, but surfaced a second, separate blocker: Gemini API bills against a **prepay credit balance** (distinct from Cloud billing), and that balance is currently $0 (`"Your prepayment credits are depleted"` from `ai.studio/projects`) | Corrected, live-schema-verified example script; Cloud billing now linked | Add prepay credits at `ai.studio/projects` → Billing (founder plans to do this in ~2 days, 2026-08-15) |

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
| GitHub curated registry | ~~Email `partnerships@github.com` requesting inclusion~~ **SENT 2026-08-15**, receipt confirmed (ticket #156426) | Sending email is explicitly excluded | Email sent by founder, referencing the live official registry listing, `server.json` remotes, source repo, and hosted endpoint; GitHub's automated system confirmed receipt same day | Awaiting GitHub's substantive response — no further action until they reply |
| xAI `grok.com/connectors` catalog | Outreach to get WhitePact into xAI's curated ~30-connector catalog | No public self-serve submission process found (researched live 2026-08-14) — likely requires a direct relationship with xAI | Live, verified end-to-end Grok integration (see `grok.md`) as supporting evidence | Decide whether to pursue outreach; no channel found to submit through directly |

## BLOCKED

| Platform | Action | Why Claude can't do it | Evidence prepared | Next step |
|---|---|---|---|---|
| Mistral Le Chat | Confirm the real, official MCP Connectors submission channel | No confirmed official channel found in research — only an unofficial community repo | `docs/adr/ADR-MISTRAL-MCP-TRANSPORT.md` documents exactly what was and wasn't confirmed | Contact Mistral directly (dev relations, official docs, or your own account) rather than treat the unofficial repo as authoritative |
