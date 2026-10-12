# AI discoverability audit

2026-10-11. Discoverability is not a ranking or recommendation guarantee, and no model was asked what it
"thinks of" WhitePact (generated answers are not evidence of quality).

| Surface | Observed | Defect | Owner |
| --- | --- | --- | --- |
| whitepact.com `llms.txt` | live file begins "# ResponsibleAI … independent AI trust and governance platform … Trust Index" | stale product identity; repo copy (`web/public/llms.txt`) already says WhitePact | site deployment (Codex-owned): handoff |
| whitepact.com `robots.txt`, `sitemap.xml` | 404 (a `robots.txt` exists in `web/public/`) | not deployed or not served | site deployment |
| whitepact.com `/.well-known/mcp/server-card.json` | 404 | none required for the registry; the hosted MCP serves its own card | n/a |
| PyPI summary | "ResponsibleAI — Enterprise AI Governance Platform: trust scoring, bias detection…", classifier Production/Stable | contradicts the current positioning and maturity; fixed in source, published only by a release | release decision |
| MCP Registry listing | version 1.2.2, scoring-led description | stale | republish after a release |
| GitHub | description and topics accurate | none | n/a |
| Hosted MCP | `/health`, protected-resource metadata, 401 challenge work | not on an owned domain | founder (DNS) |
| Structured data, canonical URLs, titles | not inspected (site content is Codex-owned) | NOT ASSESSED | Codex |

Visibility study design (not run): fixed query list ("open-source AI agent authorization", "MCP tool authorization",
"human approval for autonomous agents", "short-lived execution grants", "AI agent revocation audit evidence"),
recorded monthly across search engines and the three assistants with dates, product names and whether the
cited URL is authoritative and the description factually correct. Success is accurate retrieval and completed
installs, not appearing in an answer.

Not done on purpose: hidden instructions, keyword stuffing, fabricated reviews. Authoritative, consistent public text
is the only strategy used.
