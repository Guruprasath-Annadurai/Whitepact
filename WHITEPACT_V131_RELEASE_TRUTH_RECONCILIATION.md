# Release truth reconciliation (v1.3.1 RC)

Authoritative values for PR **#114** branch `cursor/v1.3.1-final-enterprise-hardening`.

| Field | Current verified value |
| --- | --- |
| Version | **1.3.1** |
| SHA (pre-push baseline) | `fe3c5f0ed4bcc2d4bfd5f01eda39124ee1f898b8` |
| Tree (pre-push baseline) | `ee9bdf19abee96c00a26a8bd8fa09d970b52c1cf` |
| Backend routes | **265** (`len(app.routes)`) |
| MCP production tools | **30** |
| MCP resources | **20** |
| Migrations | **61**, head **0061** |
| Frontend routes | **25** (counted from `web/src/App.tsx` route declarations) |
| SDKs | Python `rai-client`, TypeScript `@responsibleai/client`, Go `raiclient` |
| PyPI distribution name | `rai-governance-platform` |
| Python import | `responsibleai` (+ alias `whitepact`) |
| Helm chart name | `rai-governance` (chart id); metadata WhitePact 1.3.1 |
| Billing provider | Paddle (sandbox evidence historical) |
| Gate B | **False** |
| Phase7A | **False** (default off) |

## Discrepancy log

| Topic | Old report value | Current verified | Why |
| --- | --- | --- | --- |
| TypeScript SDK version | Antigravity cited **1.3.0** | package was **1.0.0** → aligned to **1.3.1** | SDK semver lagged product; not PyPI platform version |
| Python HTTP SDK version | 1.0.0 | **1.3.1** | Same SDK semver alignment |
| Migration count | 57 vs 61 | **61 / 0061** | Migrations 0058–0061 added after older inventory |
| Performance “28/30 &lt;0.5ms” | various | **29/30 LOCAL in-process** | New harness; `rai_check_trust` network-bound |
| README banner version | 1.3.0 | **1.3.1** | Maintenance RC bump |
| Browser tri-engine | implied full | **PARTIAL** | Chromium CI/journey; Firefox/WebKit not in agent VM |

Antigravity original read-only reports are **not modified**.
