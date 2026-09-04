# WhitePact MCP compatibility matrix

This is the canonical evidence boundary for client compatibility. A protocol
success is not a provider endorsement, directory listing, customer deployment,
or proof that a later WhitePact version was tested.

Status vocabulary:

- **TESTED** — the named real client/API completed the recorded path.
- **PARTIAL** — only part of the provider path completed.
- **CONFIG_READY** — configuration exists but the real provider path was not run.
- **BLOCKED** — a concrete provider, account, billing, auth, or transport gate remains.
- **UNVERIFIED** — there is no current direct evidence.

Listing/review vocabulary is separate: **LISTED**, **SUBMITTED**, **APPROVED**,
**READY_TO_SUBMIT**, or **NONE**. `APPROVED` is used only with provider evidence.

## Current WhitePact surface

| Property | Current evidence |
|---|---|
| Release tested locally | PyPI `1.2.6`, clean virtual environment, 2026-09-04 |
| Tools / resources | 30 tools / 20 advertised resources; `tools/list`, `resources/list`, and `rai_health` passed over stdio |
| Transports implemented | stdio; Streamable HTTP `/mcp`; legacy SSE |
| Hosted endpoint | Timed out during the 2026-09-04 check; do not claim current availability |
| Hosted auth design | Static Bearer key, or OIDC resource-server validation when configured; WhitePact is not an authorization server |
| Tool annotations | 30 tools declare read-only, idempotent, closed-world, non-destructive hints |
| Results | JSON text plus matching `structuredContent`; per-tool `outputSchema` is not published |
| Prompts | Not implemented |

## Client evidence

| Client / provider | Transport | Tested | Result | WhitePact / client version | Listing or review |
|---|---|---:|---|---|---|
| Generic MCP Python client | stdio | 2026-09-04 | **TESTED** — 30 tools, 20 resources, `rai_health` success | WhitePact 1.2.6 / MCP SDK 1.29.1 | Official MCP Registry **LISTED**, but latest published record is stale at listing 1.2.3/package 1.2.2 |
| GitHub Copilot CLI | Streamable HTTP | 2026-08-15 | **TESTED** — connected and invoked `rai_scan` | WhitePact hosted release then current / Copilot CLI 1.0.80 | GitHub curated inclusion **APPROVED** via support ticket; public rollout not reverified |
| Claude custom connector | Streamable HTTP | 2026-08-13 | **PARTIAL** — protocol path tested; current Claude UI path not tested | Historical hosted deployment / client version unrecorded | Anthropic directory **READY_TO_SUBMIT**; OAuth/deployment gate remains |
| Cursor | Streamable HTTP | 2026-08-15 | **TESTED** — client showed connected | Historical hosted deployment / client version unrecorded | **NONE** |
| xAI Grok API | Streamable HTTP | 2026-08-14 | **TESTED** — discovery and call reached correct plan gate | Historical hosted deployment / xAI SDK then current | Grok Build marketplace **SUBMITTED**; consumer connector listing **NONE** |
| Google Gemini Interactions API | Streamable HTTP | 2026-08-14 | **PARTIAL** — schema accepted; billing `429` prevented full call | Historical hosted deployment / model `gemini-2.5-flash` | **NONE** |
| Kiro CLI | Streamable HTTP | 2026-08-16 | **TESTED** — tools appeared in client | Historical hosted deployment / client version unrecorded | **NONE** |
| Microsoft Copilot Studio | Streamable HTTP | Not run | **CONFIG_READY** — package/configuration prepared | Not tested | Microsoft publisher submission **READY_TO_SUBMIT** after account/business gates |
| AWS Bedrock AgentCore | Streamable HTTP | Not run | **CONFIG_READY** — reference configuration only | Not tested | **NONE** |
| Mistral Le Chat | Undecided | Not run | **BLOCKED** — client transport/submission route needs current provider verification | Not tested | **NONE** |
| OpenAI / ChatGPT | Streamable HTTP | Prior submission rejected 2026-08-25 | **BLOCKED** — web/mobile review matrix and hosted endpoint must pass before resubmission | Submission was v1.2.3; v1.2.6 not provider-tested | **READY_TO_SUBMIT**, not submitted or approved |

Historical results must be rerun before claiming current v1.2.6 provider
compatibility. Use the per-client guides in this directory and record the exact
client version, WhitePact version, transport, discovered counts, and call result.
