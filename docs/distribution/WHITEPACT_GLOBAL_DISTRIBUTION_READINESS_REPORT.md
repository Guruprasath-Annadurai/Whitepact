# WhitePact global distribution readiness report

Assessed: 2026-10-11. Repository state: branch `claude/whitepact-isolation-failclosed-linux-recovery` (PR #180);
exact head is recorded in the PR description. Everything below that says "verified" was read from the live
artifact or official page on the date above; official requirements change, so each is re-read before a submission.

**Four outcomes are tracked separately** (technical compatibility, directory eligibility, published listing,
AI-assistant discoverability). **Nothing in this report is a published listing or an acceptance.**

## 1. What is actually published today (verified)

| Artifact | Live value | Source of truth in the repo | Drift |
| --- | --- | --- | --- |
| PyPI `rai-governance-platform` | latest **1.2.6**; summary "ResponsibleAI — Enterprise AI Governance Platform: trust scoring, bias detection, …"; classifier **Production/Stable**; releases 0.9.0–1.2.6 | `pyproject.toml` 1.3.1 (unpublished), description already WhitePact-first, classifier changed to Beta | Published metadata still carries the old identity and the Production/Stable claim until a new release is cut (not authorized) |
| MCP Registry `io.github.Guruprasath-Annadurai/whitepact` | listing version **1.2.2**; description scoring-led; stdio package 1.2.2 | `server.json`: listing 1.2.3, package 1.2.2 | Three different version numbers (registry 1.2.2, manifest 1.2.3/1.2.2, PyPI 1.2.6, pyproject 1.3.1). `server.json` description and `tool_count` corrected in this pass; versions are a release-time decision (`tests/test_server_json.py` guards direction) |
| Hosted MCP `whitepact-mcp-http.onrender.com` | up; `/health` reports 30 tools, Streamable HTTP + SSE; RFC 9728 protected-resource metadata served; `/mcp` without credentials returns 401 with a `WWW-Authenticate` challenge | `server.json` remotes | Runs previously published code, **not this candidate**; the host is a Render subdomain, **not a domain WhitePact owns** (see §3) |
| GitHub repo | description "open-source runtime authority for AI agents…", MIT, 14 topics, homepage whitepact.com | n/a | consistent |
| whitepact.com | up; **`llms.txt` still says "# ResponsibleAI … Trust Index"**; `robots.txt` and `sitemap.xml` return 404; `/.well-known/mcp/server-card.json` 404 | `web/public/llms.txt` already says WhitePact | The deployed site is older than the repository. The website is Codex-owned: handoff only, no change made here |
| OpenSSF Best Practices | project 14112, level **silver** (self-attested, last updated 2026-08-29) | see `docs/assurance/WHITEPACT_OPENSSF_GAP_ANALYSIS.md` | 31 criteria unmet or unanswered |
| OpenSSF Scorecard | **7.4** (2026-10-06, commit `38f92722` = `main`) | see gap analysis | Signed-Releases 0, Fuzzing 0, Vulnerabilities 0 (21), Contributors 0, Pinned-Dependencies 5 |
| Release provenance | v1.2.6 wheel and sdist: SHA-256 OK; `gh attestation verify` passes (SLSA provenance v1, reusable-build workflow, source digest, tag ref, hosted runner); a wrong source digest is refused; CycloneDX 1.6 SBOM (43 components) attested | `docs/VERIFY_RELEASE.md` | Verified by me on 2026-10-11 |

## 2. Platform by platform

| Platform | Mechanism (official, read 2026-10-11) | Eligibility today | Status | What blocks it |
| --- | --- | --- | --- | --- |
| **OpenAI / ChatGPT** | Plugin directory: upload a plugin ZIP in the platform portal, automated metadata and MCP-tool scans, submit for review, publish after approval. Needs a verified developer identity (individual or business), domain-verification challenge for the MCP server URL, and a demo account with sample data | **NOT READY** | no ZIP built; no domain the project owns for the MCP URL; identity verification is a founder action; the advertised tools are an analysis toolkit, not the authority product; no ChatGPT connection was tested | §3, §4 |
| **Anthropic / Claude** | Directory submission portal (open to developers on paid Claude plans): single remote MCP connector or a plugin bundle; Software Directory Policy applies (safety, compatibility, developer requirements, MCP-specific requirements incl. OAuth 2.0, annotations, ≤64-character tool names, a standard test account, ≥3 example prompts, verified ownership of endpoints) | **NOT READY** | no Claude connection was tested; the hosted endpoint's domain is not owned; Claude states it supports the newest MCP specification ("MCP 2.0") while the pinned SDK (`mcp<2`) speaks up to 2025-11-25: compatibility with Claude is untested | §3, §4 |
| **xAI / Grok** | Custom MCP connector at grok.com/connectors → New Connector → Custom, public HTTPS MCP URL, OAuth where required; Business/Enterprise admins provision connectors. The connectors page lists built-in connectors and a *curated catalog*; **no public third-party submission programme is described** | **CUSTOM CONNECTOR POSSIBLE — NOT TESTED; PUBLIC DIRECTORY PATH UNVERIFIED** | no Grok session was available to test | needs a tester account and the owned-domain endpoint |
| Google Gemini, Perplexity, Cursor, other coding agents | not researched in this pass | NOT ASSESSED | no claim is made |
| **Official MCP Registry** | `server.json` published with the registry CLI (namespace `io.github.<owner>/<name>` authenticated through GitHub) | **LISTED, STALE** | listing 1.2.2 with a scoring-led description; republishing needs a PyPI release that matches and founder authorization | release decision |
| Smithery, Glama, others | not verified in this pass | NOT ASSESSED | existing listings must be inspected before any new submission |

## 3. Blockers that are not engineering

1. **Own the endpoint domain.** Anthropic's policy (3.F) and OpenAI's domain-verification step both require proof
   that the publisher controls the server URL. `…onrender.com` is not WhitePact's domain. Needs a DNS decision
   (e.g. an `mcp.` subdomain of the project's domain) and DNS access: **founder action; I will not change DNS.**
2. **Developer identity verification** (OpenAI organization verification, Anthropic paid plan): founder action.
3. **Test account with sample data** for reviewers (both programmes): must be created in a non-production tenant
   by the founder; I will not create credentials in the live service.
4. **Privacy policy URL, support contact, terms**: files exist (`PRIVACY_POLICY.md`, `SECURITY.md`,
   `TERMS_OF_SERVICE.md`); they must be served from the owned domain and reviewed by whoever carries the legal
   responsibility. Their content was not legally reviewed here.

## 4. Engineering findings that would cause rejection or user harm (and what was done)

| Finding | Evidence | Status |
| --- | --- | --- |
| The MCP surface is the older scoring toolkit; **none of the 30 advertised tools lets an assistant inspect configured authority, explain/simulate a policy decision, review approvals or retrieve evidence** | tool table in the submission package | **OPEN, design decision.** Implementing control-plane read tools means a read path that does not run inside the isolated executor; that is a boundary change I will not make without a decision. Proposal in `MCP_DIRECTORY_SUBMISSION_PACKAGE/README.md` |
| `rai_incident_log` description said it logs/creates records; it only builds one, and its output told the caller to POST elsewhere | `tools.py` | **Fixed**: honest description, descriptive persistence note, regression test |
| Manifest `tool_count` 31 (30 are advertised) and a scoring-led description | `server.json` | **Fixed** with a test against `production_tool_count()` |
| Manifest remote said "create a free org" for an API key; free organizations have **zero hosted quota** by design | `licensing.py`, `server.json` | **Fixed**: states hosted entitlement is required and stdio is advisory |
| API-key bearer is the only remote credential in the manifest; Anthropic requires OAuth 2.0 for authenticated remote servers | existing OAuth authorization server (reviewer scope) is implemented and tested (30 tests) | **Partly open**: the OAuth path exists for review use; the registry manifest does not advertise it |
| Tool names carry a legacy `rai_` prefix (old brand); renaming breaks users | 30 tools | **Accepted, documented**; any rename needs a deprecation window |
| Machine-checkable directory rules applied to every advertised tool: explicit boolean hints, descriptions ≥ 60 chars, no steering vocabulary, no pricing, no conversation-history inputs, unique names, no generic executor | `tests/test_mcp_directory_conformance.py` (34) | **PASS** (a precondition, not an acceptance) |
| Request/trace identifiers appear in some error bodies (OpenAI asks tools to avoid internal identifiers in responses) | `request_id` in REST errors | NOT CHECKED for MCP tool responses |

## 5. Technical compatibility actually tested

Reference MCP client (`mcp` 1.29.1 Python SDK) against the real hosted application, in-process: initialize at four
protocol versions, tools/list, resources/list, validation, authentication, tenant isolation, OAuth flow
(`docs/launch/MCP_COMPATIBILITY_MATRIX.md`). **No third-party assistant (ChatGPT, Claude, Grok, Gemini, Cursor) was
connected.** Those rows are NOT TESTED.

## 6. Next actions in order

1. Founder: decide the owned MCP hostname and provide DNS; create a non-production reviewer tenant.
2. Decision: the authority-review read tools (design in the package README).
3. Re-run `tests/test_mcp_directory_conformance.py` after any tool change; re-read the three official policies.
4. Cut a release only on authorization; then republish the registry listing with matching versions.
5. Test with a real ChatGPT developer-mode connector, a real Claude custom connector and a real Grok custom
   connector; record versions and results in the compatibility matrix.
