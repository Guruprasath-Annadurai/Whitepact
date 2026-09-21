# External directory metadata — canonical sources

Third-party listings (MCP Registry, Smithery, Glama, MCPNav, MCPBeat) should ingest:

| Field | Canonical source |
|-------|------------------|
| MCP endpoint | `distribution/platform-metadata.yaml` → `mcp_endpoint.streamable_http` |
| Tool list | Live `/.well-known/mcp/server-card.json` OR `TOOL_DEFS` via release |
| Tool counts | `src/responsibleai/mcp/metadata.py` (`public_count` / `registered_count`) |
| Product version | `pyproject.toml` / `responsibleai.__version__` |
| Short description | `distribution/platform-metadata.yaml` `short_description` |
| License | GitHub `licenseInfo` (MIT) |
| Auth | Bearer API key + optional OAuth (see `/.well-known/oauth-protected-resource`) |

## Stale fields corrected this pass

- `distribution/platform-metadata.yaml` — removed `27 tools`, aligned version to 1.3.0
- Added `mcp/metadata.py` as count source of truth

## Do not manipulate third-party caches via code

Republish listings after release tags only.
