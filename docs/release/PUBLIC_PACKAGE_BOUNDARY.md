# Public package boundary (V1)

Factual technical boundary for `rai-governance-platform` on PyPI. Not a commercial blueprint.

## What V1 ships publicly (MIT)

- Python package `rai-governance-platform` / console entrypoints `whitepact`, `whitepact-mcp`
- Governance core, dashboard (optional extra), MCP server, public schemas and examples
- Published release line: **1.2.6** (PyPI); source tree may read **1.3.0** until next publish

## What remains supported

- Existing MIT installs and documented public APIs
- No yank or license retroactivity on historical wheels

## Hosted / enterprise

- Hosted MCP (`whitepact-mcp-http.onrender.com`) may run a published or pinned deploy line under separate operational terms
- Future enterprise or hosted components may use different terms when clearly labeled

## SDK / client surfaces that can stay public

- MCP integration docs, HTTP/SSE transports, server-card metadata
- Public adapters and examples under `docs/integrations/`

## Compatibility

- Post-V1 package naming may be additive; see `docs/POST_V1_PACKAGE_MIGRATION.md`
- Do not split or yank `rai-governance-platform` pre-V1 release
