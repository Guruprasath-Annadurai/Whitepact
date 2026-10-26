# Smithery and Glama listing review (read-only, 2026-10-11)

Founder list item: "Smithery/Glama listing review". I read the public pages only. **Nothing was submitted, claimed,
edited or paid for**, and no account was created. Changing either listing is a founder action.

## Smithery — `guruprasathannadurai-official/whitepact`
| Observed | Assessment |
|---|---|
| Listing exists; "last deployed 2 months ago"; quality score **42/100**; description **"No description"** | Weak first impression; the page tells a buyer nothing. |
| **27 tools, 20 resources** shown | The server now has **30** production tools (and 4 more authority tools only on governed hosted connections). The listing is stale. |
| Tool texts are the older "ResponsibleAI" wording (e.g. `rai_incident_log`, `rai_audit_summary` describe the pre-recovery behaviour) | Descriptions predate the truthfulness fixes in this branch (stdio advisory, incident-log scope). They may over-claim relative to current code. |
| No authentication shown; "Try now" offered | The listing implies a server a user can try. The official hosted endpoint is **not** qualified (see `MCP_HOSTNAME_RUNBOOK.md`); do not point Smithery at the old hosted service as if it were production. |
| Brand shown as "whitepact" with ResponsibleAI-era descriptions | Brand inconsistency with the current WhitePact positioning. |

Recommendation (founder): do not edit until a qualified endpoint exists; then publish a fresh server card
(`/.well-known/mcp/server-card.json` already serves one generated from the live definitions), add a real description,
and let Smithery rescan. Until then consider *unlisting or marking the listing as stale* rather than letting 27-tool
descriptions stand.

## Glama — `Guruprasath-Annadurai/Whitepact`
| Observed | Assessment |
|---|---|
| Auto-indexed from the GitHub repository; "Updated 12 hours ago"; license/quality/maintenance badges all **A**; MIT | Healthy; this is Glama's own scoring, not an independent audit. |
| Description: governance, trust-scoring, compliance, guardrail, cost, drift and supply-chain tools over stdio, Streamable HTTP or legacy HTTP+SSE; "routes every tool call through a deterministic five-way decision ... with hash-chained evidence, human approval workflows" | Derived from the README. **Two over-statements to check against current truth:** (1) the five-way decision applies to the *hosted governed* path; the stdio server is advisory (documented in `server.json` and `LOCAL_STDIO_MCP_SCOPE.md`); (2) "hash-chained evidence" is internal consistency only, not externally anchored. |
| Tool list includes `rai_memory_write_check`, `rai_benchmark`, `rai_audit_summary` | Matches code names; descriptions not re-verified line by line. |
| Stars/forks shown (30 / 2 at scrape) | No claim made. |

Recommendation: fix the **README wording** that Glama copies (stdio advisory; evidence not externally anchored), then let
Glama re-index. That is a repository change I can make, but it touches the public README/website boundary, so I am
leaving it as a proposal for the Codex/website owner rather than editing it here.

## Neither listing should be used as evidence of
Production readiness, certification, third-party endorsement or ChatGPT/Claude/Grok compatibility.
