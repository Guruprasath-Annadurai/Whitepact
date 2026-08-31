# WhitePact MCP distribution status — 2026-08-31

This file is a time-stamped owner-side distribution snapshot. It separates verified listings/submissions from compatibility-only integrations and from actions that still require the founder's authenticated account or legal identity.

## Canonical submission metadata

- Product: WhitePact
- Repository: `Guruprasath-Annadurai/Whitepact`
- MCP server identity: `whitepact`
- Official MCP Registry namespace: `io.github.Guruprasath-Annadurai/whitepact`
- Current source-of-truth capability count: **30 tools / 20 resources**
- Current hosted MCP transport documented by the repo: Streamable HTTP `/mcp`, with legacy HTTP+SSE retained for older clients
- Self-hosted transport: stdio via `whitepact-mcp` (legacy alias `responsibleai-mcp` retained)
- License: MIT

### Tool-count evidence

The current 30-tool count is grounded in repository history, not marketing copy:

- `3b02dffa1ee04510c8db95d53e5a563c81e76407` added `rai_memory_write_check` and `rai_memory_read_check`, taking the server from 27 to 29 tools.
- `5bb11a78d7965e8bcef10432bc411b85918a3f8d` added `rai_causal_influence_check` as the 30th tool and updated hardcoded tool-count assertions/server metadata from 29 to 30.
- `eb64e1c8123bc017309f32ddcf6e57b69f59ac19` later audited the OpenAI review contract and explicitly recorded the actual count as 30.
- `src/responsibleai/mcp/server.py` returns `TOOL_DEFS` directly from `list_tools()`.

Known doc drift remains in README: its MCP overview and Smithery listing say 30 tools, but the `Available tools (27)` heading/table still omits the three tools above. Do not submit 27 as the current count.

## Already submitted / listed

### Official MCP Registry — LIVE

WhitePact is already published in the official MCP Registry under `io.github.Guruprasath-Annadurai/whitepact`. No new initial submission is required. Future registry updates should publish a version whose package/release metadata matches the exact artifact being advertised.

### Smithery — LIVE

WhitePact is already listed on Smithery. Repository documentation records the hosted Streamable HTTP scanner discovering **30 tools / 20 resources**.

### xAI Grok Build plugin marketplace — OPEN SUBMISSION, UPDATED

`xai-org/plugin-marketplace#244` remains open. On 2026-08-31 its head branch was updated to correct stale 27-tool documentation to the current **30 tools / 20 resources** and to narrow an over-broad statelessness claim. This is a submission to the Grok Build coding-agent marketplace, not the consumer `grok.com` connector catalog. Do not describe the plugin as accepted until xAI merges/accepts it.

### GitHub MCP Registry curated inclusion — APPROVED, PUBLIC ROLLOUT PENDING VERIFICATION

GitHub Support ticket **#156426** was approved on 2026-08-27. GitHub's Senior Partner Engineer wrote that the WhitePact MCP server had been reviewed and **approved for inclusion in the GitHub MCP Registry**, that GitHub would proceed with adding it, and that no further action was required from the submitter.

This is a verified approval signal from GitHub, but a fresh public search on 2026-08-31 did not yet surface a WhitePact listing under the GitHub MCP catalog. Therefore the accurate current claim is **approved for inclusion; rollout/listing pending public verification**, not yet “publicly listed in GitHub MCP Registry.”

## OpenAI / ChatGPT — RE-SUBMISSION REQUIRED

The first WhitePact ChatGPT app/plugin submission (v1.2.3) was received on 2026-08-13 and rejected on 2026-08-25. The reviewer reason was specific: one or more submitted test cases did not produce the documented expected results, and OpenAI instructed the submitter to re-run all submitted tests and align tool behavior/output across ChatGPT web and mobile before resubmitting.

Repository remediation after that submission includes commit `eb64e1c8123bc017309f32ddcf6e57b69f59ac19`, which:

- corrected `rai_trust_score` output-contract naming additively;
- added source-contradiction support to `rai_hallucination` for the submitted hallucination test;
- corrected the misleading `rai_org_status` contract documentation;
- hardened `rai_compliance` / `rai_eu_ai_act_classify` routing descriptions;
- added `tests/openai_review/` as a machine-checked regression suite for the submitted test contract;
- recorded 30 as the actual MCP tool count.

A follow-up commit, `84aa6506dabd0056cf1b2b874a9e9eb09f158fb0`, wired `rai_org_status` to authenticated hosted-org state and added live MCP protocol tests for that path.

A current re-submission matrix is maintained in `compliance/OPENAI_RESUBMISSION_2026-08-31.md`. It requires the exact positive/negative cases to be re-run in ChatGPT web and mobile using the actual review endpoint/auth mode before a new submission is sent.

**Owner action required:** run that web/mobile matrix and re-submit through the authenticated OpenAI app submission UI after observed outputs are aligned with the form.

## Anthropic / Claude — FOUNDER UI SUBMISSION REQUIRED

WhitePact is already compatible with Claude custom connectors, but curated directory publication requires the founder's authenticated Claude/Anthropic account and the current Connectors Directory submission flow. The repository has setup documentation under `docs/integrations/claude.md`.

Before submission, verify the hosted endpoint with current `tools/list` and use **30 tools / 20 resources** in any manual metadata.

## Microsoft Copilot — FOUNDER / PUBLISHER ACTION REQUIRED

Two separate routes exist in the repository's integration plan:

1. private/custom connector use in a Microsoft tenant (interactive tenant/admin action), and
2. public/certified connector distribution through Microsoft's publisher/Partner Center process.

The repository contains a prepared package under `distribution/microsoft/`. Final public certification requires the appropriate Microsoft publisher identity/business verification and authenticated submission.

## Gemini / Google — COMPATIBILITY, NOT A VERIFIED PUBLIC DIRECTORY SUBMISSION

The repository contains a Gemini remote-MCP integration example and records that the live Gemini API accepted the corrected MCP tool configuration after two implementation fixes. Remaining live testing was account/billing constrained in the recorded test session.

Do not describe this as a Google marketplace listing unless Google has actually accepted WhitePact into a public catalog. Custom/private MCP connectivity and public directory publication are different claims.

## Cursor / Kiro / GitHub Copilot CLI / Grok API — VERIFIED CLIENT INTEGRATIONS, NOT MARKETPLACE ADOPTION

The repository records successful client-side integrations for Cursor, Kiro CLI, GitHub Copilot CLI, and the xAI/Grok API path. These are compatibility evidence only. They do not imply vendor endorsement, partnership, user adoption, or curated marketplace acceptance.

## Next execution order

1. Reconcile the README `Available tools (27)` table with the 30-tool source of truth.
2. Re-run the exact OpenAI review test contract against the current hosted endpoint and ChatGPT web/mobile.
3. Founder re-submits OpenAI app after those tests pass.
4. Founder submits to Anthropic's current Connectors Directory flow.
5. Complete Microsoft publisher/Partner Center prerequisites and submit the prepared Microsoft package.
6. Verify when GitHub's approved curated listing becomes publicly visible and only then change the claim from “approved” to “live.”
7. Continue only legitimate community-directory submissions that have an explicit public submission mechanism; do not spam directories or fabricate acceptance.

## Claim boundaries

- Official OpenSSF Best Practices status must remain **Silver** unless the public project record changes.
- OSPS Baseline must remain **Level 1** unless the public project record changes.
- A directory listing is not adoption.
- A successful client integration is not a partnership or endorsement.
- Package/download counts are not user counts.
- A submitted PR or form is not an accepted listing until the platform says so.
