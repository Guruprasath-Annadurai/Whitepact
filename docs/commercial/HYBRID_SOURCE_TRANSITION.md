# Hybrid closed-core transition (design only — no repo split executed)

## Strategy

WhitePact remains **historically public MIT** in this repository. Future proprietary
evolution moves behind a **controlled service boundary**, not retroactive secrecy.

```
PUBLIC SURFACE (docs, SDKs, contracts, adapters, examples)
        |
        |  authenticated API / MCP
        v
CONTROLLED SERVICE BOUNDARY (hosted MCP, future control plane)
        |
        v
PRIVATE FUTURE CORE (premium enforcement, hosted runtime internals)
```

## Non-goals (this pass)

- No LICENSE change
- No repository visibility change
- No history deletion
- No package yank
- No flag-day API break

## Phased migration

1. **Now** — canonical metadata, honest positioning, directory-facing consistency.
2. **V1 release** — stabilize contracts (`contracts/`, Sovereign TS SDK, MCP tool registry).
3. **Post-V1** — introduce optional remote authority backend; keep local MIT path for dev.
4. **Later** — new private repo or submodule for premium core; public repo becomes thin client + docs.

## Compatibility preservation

- Keep `responsibleai-mcp` / `whitepact-mcp` entry points.
- Keep MCP tool names stable; version via `mcp/metadata.py`.
- Document breaking changes in CHANGELOG only with release tags.
