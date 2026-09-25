# WhitePact package identity (source of truth)

## Product vs distribution

| Concept | Value |
| --- | --- |
| **Product name** | WhitePact |
| **PyPI distribution (platform)** | `rai-governance-platform` |
| **Canonical Python import** | `responsibleai` |
| **Compatibility import alias** | `whitepact` (re-exports `responsibleai`; same objects) |
| **CLI (preferred)** | `whitepact` |
| **CLI (legacy)** | `biasbuster` |
| **MCP entrypoints** | `whitepact-mcp`, `whitepact-mcp-http` |
| **HTTP API SDK (Python)** | PyPI package `rai-client` → import `rai_client` |
| **HTTP API SDK (TypeScript)** | npm `@responsibleai/client` |
| **HTTP API SDK (Go)** | module path in `sdk/go/go.mod` → `raiclient` |
| **Helm chart name** | `rai-governance` (historical chart id; metadata describes WhitePact) |

## What to install

```bash
# Platform + dashboard (from PyPI when published)
pip install "rai-governance-platform[dashboard]"

# HTTP client SDK (from repo path or future PyPI rai-client)
pip install ./sdk/python

# TypeScript client (from repo)
cd sdk/typescript && npm ci && npm run build

# Go client
cd sdk/go && go test ./...
```

Do **not** use `pip install whitepact` unless PyPI documents that distribution as supported.
The in-tree `whitepact` package is an import alias shipped inside `rai-governance-platform`.

## What to import

```python
import responsibleai
from responsibleai.mcp.tools import dispatch_tool

# Optional alias (identical objects):
import whitepact
```

## Version alignment (1.3.1 RC)

| Surface | Version field |
| --- | --- |
| `pyproject.toml` / `responsibleai.__version__` | 1.3.1 |
| `web/package.json` | 1.3.1 |
| `sdk/python/pyproject.toml` | 1.3.1 |
| `sdk/typescript/package.json` | 1.3.1 |
| Docker `WHITEPACT_VERSION` | 1.3.1 |
| Helm `appVersion` | 1.3.1 |

SDK packages use their own semver for API-client releases but are aligned to **1.3.1** for this maintenance RC.
