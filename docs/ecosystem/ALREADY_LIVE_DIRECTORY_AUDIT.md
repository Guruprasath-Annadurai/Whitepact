# Already-live directory audit

Verified on 2026-10-09. “Live” means the authoritative page or API returned
the project. A search snippet alone is not enough, so MCPBeat and
AlternativeTo stay unverified.

Do not create a second listing for any row in this file.

## Official MCP Registry

- URL: https://registry.modelcontextprotocol.io/v0/servers?search=io.github.Guruprasath-Annadurai/whitepact&version=latest
- Name: `io.github.Guruprasath-Annadurai/whitepact`
- Status: `active`, `isLatest: true`
- Published listing version: `1.2.3` (updated 2026-08-12)
- Package pin: `rai-governance-platform` `1.2.2`
- Remotes: `https://whitepact-mcp-http.onrender.com/mcp` and `/sse`
- Publisher tool count stored on that listing: 27

Correction prepared in `server.json`, not published:

- Listing version `1.2.6`
- Package pin `1.2.6`, which is the newest PyPI release and contains
  `whitepact-mcp`
- Remote text no longer tells a visitor to create a free org. The host
  still requires a bearer token.
- Tool count in the manifest stays 31 because that is `len(TOOL_DEFS)`,
  including `test.counter.increment`. The hosted card advertises 30.

Owner step: `mcp-publisher` login and publish after review. This lane did
not run the publisher.

## Glama

- URL: https://glama.ai/mcp/servers/Guruprasath-Annadurai/Whitepact
- HTTP 200, title `WhitePact by Guruprasath-Annadurai | Glama`
- The page includes repository README text, which mixes “30 tools” with
  “Available tools (27)”.

Correction: after the registry manifest is published, refresh this existing
server. Do not add another Glama server. Tell the owner the accurate public
split: 30 tools on the hosted card, 31 definitions in source, 10 canonical
resources advertised as 20 URIs.

## Smithery

- URL: https://smithery.ai/servers/guruprasathannadurai-official/whitepact
- HTTP 200, title `whitepact - MCP | Smithery`
- Visible text: `guruprasathannadurai-official/whitepact`, published Aug 12,
  2026, “No description”, score 42/100
- The README badge still points at
  `https://smithery.ai/server/guruprasathannadurai-official/whitepact`
  (singular `server`). That URL redirected to `servers` during this audit.

Correction: edit the existing Smithery server’s description using the
MCP-focused paragraph in `copy/DESCRIPTIONS.md`. Do not create a second
server. A README badge URL update is optional and was not required to make
the listing exist.

## MCP Market

- URL: https://mcpmarket.com/server/whitepact
- HTTP 200, title `Whitepact: AI Governance, Trust, & Compliance Platform`
- The page names Guruprasath-Annadurai and says “Claim this listing”.
- `https://mcpmarket.com/servers/whitepact` returned 404. The live path is
  `/server/whitepact`.

Correction: claim the existing page. Do not submit another WhitePact server.
The claim flow’s price was not shown, so do not pay.

## MCPBeat

Not classified as live. `https://mcpbeat.com/mcp-servers/guruprasath-annadurai/whitepact/`
returned HTTP 403 to this host. A web index showed a page that claimed 27
tools and a PyPI install rate. Those numbers were not re-read from the
origin and must not be copied into our own claims.

## AlternativeTo

Not classified as live. The software URL and the search URL returned HTTP
403. Do not suggest a new AlternativeTo entry until a person confirms the
name is absent.

## OpenSSF Best Practices

- URL: https://www.bestpractices.dev/projects/14112
- JSON: `badge_level` `silver`, passing percentage 100, updated 2026-08-29
- Project name WhitePact, repository the GitHub project above

Correction: keep calling this a Best Practices badge. Do not call it a
certification, and do not claim gold.

## PyPI

- URL: https://pypi.org/project/rai-governance-platform/
- Latest `1.2.6`, MIT, requires Python `>=3.11`
- Summary still says “ResponsibleAI — Enterprise AI Governance Platform”
- Classifier includes `Development Status :: 5 - Production/Stable`
- `whitepact` on PyPI does not exist

Correction for a future release, not performed here:

- Keep the project name `rai-governance-platform`
- Point the summary at WhitePact without saying the hosted enterprise
  service is globally available
- Publish the source classifier only when a release is authorized
- Do not upload `1.3.1` from this branch

## GitHub topics

Fourteen topics are already on the repository. They are listed in
`inventory.json`. No source change can set topics. Optional additions that
stay accurate: `python`, `mit-license`. The topic cap is 20.

## Hosted endpoint used by several of these listings

The endpoint is up and authenticated. It is not a substitute we deployed.
Server card on 2026-10-09:

- `serverInfo.name`: `whitepact`
- `serverInfo.version`: `1.3.1` (running host, not PyPI)
- authentication required: oauth2 and apiKey
- tools: 30
- resources: 20
