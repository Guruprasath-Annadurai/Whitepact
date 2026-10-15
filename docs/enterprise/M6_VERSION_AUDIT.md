# M6 version consistency audit

| Surface | Value | Notes |
|---------|-------|--------|
| Python (`pyproject.toml`) | `1.3.1` | Distribution `rai-governance-platform` |
| CLI entry | `whitepact` → `whitepact.cli:main` | Legacy `biasbuster` / `responsibleai` documented |
| MCP entry | `whitepact-mcp` | Same server module as enterprise MCP |
| Release candidate | M6 branch `cursor/whitepact-m6-final-engineering-rc-f7a9` | Not published to PyPI/npm |

Frontend/Helm/Docker: verified in CI build jobs on exact-head; no separate version bump in M6 unless drift found.
