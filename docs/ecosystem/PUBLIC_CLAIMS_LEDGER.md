# Public claims ledger

Checked on 2026-10-09 against live sites and commit
`35488a68e587df2adfdb1ceaad44001faca524a4`.

## Versions

| Surface | Observed value | How it was checked |
|---|---|---|
| Source `pyproject.toml` `version` | `1.3.1` | File at the frozen commit |
| PyPI `rai-governance-platform` latest | `1.2.6` | `https://pypi.org/pypi/rai-governance-platform/json` |
| PyPI project `whitepact` | Not found (HTTP 404) | `https://pypi.org/pypi/whitepact/json` |
| PyPI `rai-client` | Not found (HTTP 404) | `https://pypi.org/pypi/rai-client/json` |
| npm `whitepact` | Not found (HTTP 404) | `https://registry.npmjs.org/whitepact` |
| Official MCP registry latest | Listing `1.2.3`, package pin `1.2.2`, `isLatest: true` | Registry search API |
| `server.json` in this branch | Listing `1.2.6`, package pin `1.2.6` | Proposed correction, not published |
| `whitepact.com` `/api/health` | `version` `1.2.6`, `status` `healthy` | GET on 2026-10-09 |
| Hosted MCP server card | `serverInfo.version` `1.3.1`, 30 tools, 20 resources, authentication required | GET `https://whitepact-mcp-http.onrender.com/.well-known/mcp/server-card.json` |
| Docker Hub search `whitepact` | `count` 0 | Hub search API |
| GitHub stars | 2 | GitHub repository API |

The hosted server card’s `1.3.1` string matches the source tree. It does not
make `1.3.1` a PyPI release. Install instructions stay on `1.2.6`.

## Entrypoints in the published 1.2.6 wheel

The wheel `rai_governance_platform-1.2.6-py3-none-any.whl` contains:

```text
whitepact = biasbuster.cli:main
whitepact-mcp = responsibleai.mcp.server:main
whitepact-mcp-http = responsibleai.mcp.server:main_http
```

Source `1.3.1` maps `whitepact` to `whitepact.cli:main`. That mapping is not
what the published wheel does. Public install text must not pretend it does.

## Tool and resource counts

| Count | Meaning |
|---|---|
| 31 | `len(TOOL_DEFS)` in source, including `test.counter.increment` |
| 30 | Production tools, and the count on the hosted server card |
| 10 | Canonical resources |
| 20 | Advertised resource URIs (`whitepact://` and `rai://`) |
| 27 | Older public listings (registry publisher metadata and some directory mirrors) |

`CONTRIBUTING.md` previously said 27 tools. It now states the 31 / 30 split.
`server.json` `_meta.tool_count` stays 31 because `tests/test_server_json.py`
locks it to `len(TOOL_DEFS)`.

## Development status classifier

Live PyPI `1.2.6` includes `Development Status :: 5 - Production/Stable`.

That Trove classifier is not a statement that the hosted enterprise service
has global production authorization. It is also not a SOC 2 claim, a customer
claim, or a promise of complete runtime protection.

This documentation commit leaves the source classifier unchanged so the
metadata edit can stay in its own commit. The following commit on this branch
sets the source classifier to `Development Status :: 4 - Beta` because source
`1.3.1` is unpublished and the hosted enterprise release is still under
operational qualification. Republishing PyPI is out of scope, so the live
`1.2.6` classifier remains Production/Stable until a later release.

## Hosted MCP remote

`POST /mcp` and `GET /sse` on `https://whitepact-mcp-http.onrender.com`
returned HTTP 401 with `{"error":"unauthorized","message":"Provide a valid Bearer credential."}`.
The protected-resource metadata URL is
`https://whitepact-mcp-http.onrender.com/.well-known/oauth-protected-resource`.

The previous remote description said a visitor could create a free org and
copy a key from Settings. That signup path was not verified. The description
in `server.json` now says a bearer credential is required and that a public
self-serve signup was not verified. The remote URLs stay, because the host
answered.

## Website

`https://whitepact.com` resolved to `216.24.57.1` and returned HTTP 200.
The HTML title is `ResponsibleAI · Governance Dashboard`. It is a JavaScript
dashboard, not the qualified marketing site stored under `web/`. Do not
submit marketing screenshots as pictures of this live site.

`https://whitepact.ai` and `https://whitepact.dev` did not resolve.

## Claims that remain forbidden

Do not say the project is globally production-certified, SOC 2 certified,
guaranteed secure, used by Fortune 500 enterprises, 100% runtime protection,
or that production SaaS is available worldwide. Those statements were not
verified. The OpenSSF result that was verified is a Best Practices silver
badge for project 14112, which is a self-assessed project badge.

## GitHub identity

Default branch: `main` at `38f927229b4ea53d19a9107c78653307f5263629` on
2026-10-09. License: MIT. Discussions: enabled. Homepage setting:
`https://whitepact.com`. Description: “WhitePact — open-source runtime
authority for AI agents and autonomous systems. Intelligence may propose;
WhitePact decides.”
