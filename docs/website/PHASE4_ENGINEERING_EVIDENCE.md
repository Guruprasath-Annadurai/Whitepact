# Phase 4 engineering evidence boundary

This is repository-side launch integration readiness, not deployment approval,
independent qualification, certification, or production readiness.

## Source and isolation

- Qualified Phase 3 base: `9a721aa078daba5d554120d7aeb61d5febcdcc79`.
- Base tree: `b2d7f3c27c7044be38dc261d5e00ede0a8cb9b9c`.
- Phase 4 branch: `codex/whitepact-global-website-phase4-launch-integration`.
- PRs 143 and 145 and their branches are not changed by this work.
- Product Python, governance, authority, dispatcher, MCP, SDK and CLI source
  remain unchanged. Generated website assets live in the existing dashboard
  static directory; their rebuild is not a runtime architecture change.

Exact candidate/tree and exact-head workflow links are recorded in the Phase 4
draft PR after commit, avoiding a self-referential commit hash in these files.

## Implemented repository controls

Central validated public origin/profile configuration drives client metadata,
static HTML, discovery files and route inventory. Non-production profiles are
noindex. Only explicitly public Vite variables are admitted; server secrets are
not frontend configuration. Production source maps remain disabled.

The launch tooling supplies deterministic SHA-256 manifests, asset retention
checks against qualified Phase 3, self-only public CSP/header/cache contracts,
an isolated local preview smoke, and an explicitly targeted read-only future
HTTPS acceptance harness. The HTTPS browser harness is prepared, not claimed
externally passed. Local HTTP cannot prove TLS, DNS, Cloudflare configuration,
origin protection, real compression, rollback deployment or field CWV.

Security-contact validation requires explicit owner approval and future UTC
RFC3339 expiry. No security.txt is published. Maintenance HTML is an artifact;
an operator must configure real HTTP 503/no-store/Retry-After behavior.

## Fresh local validation

| Gate | Evidence |
| --- | --- |
| Frontend | ESLint, TypeScript and production build passed; 101 Vitest tests passed |
| Launch contracts | 11 Node tests passed; includes route/router agreement, tamper detection, retained old/new assets, owner-contact gate and unsafe target rejection |
| Local acceptance | 15 public routes, real 404, private shell, discovery and refund redirect passed |
| Staging | Explicit HTTPS staging origin build/audit passed; production output restored |
| Python web regression | 71 relevant tests passed, including disposable localhost PostgreSQL; no SQLite substitution |
| Accessibility/responsive | Existing local suite covers 150 scans at ten widths, plus no-JS, blocked assets, keyboard, zoom, delayed hydration, clipboard denial and reduced motion |
| Dependencies | Full and production-only npm audit: zero advisories after compatible source-map-js 1.2.2 patch |
| Static policy | Pinned actions, documentation consistency, SPDX and workflow syntax checked |
| Clean reproducibility / exact-head CI | Required before engineering handoff; results and identities recorded in draft PR |

The first loopback smoke attempt was denied by the execution sandbox (EPERM),
then passed with permission to bind a temporary localhost server. No TLS
validation bypass was introduced. Initial TypeScript integration errors were
fixed before the passing build; no compiler rules were disabled.

## Performance and disclosure

Local lab medians: mobile LCP 2436 ms, desktop 448 ms; mobile CLS zero and
desktop CLS approximately 0.00002. Transfer was 652122 bytes. This is close to,
not a claimed improvement over, Phase 3's observed lab results; transfer rose
slightly. Measurements are local lab observations, not field CWV or INP proof.
Deterministic chunk gzip budgets are enforced separately from noisy lab timing.

## Owner and external gates

The authoritative register is [PHASE4_LAUNCH_CHECKLIST.md](PHASE4_LAUNCH_CHECKLIST.md).
Legal identity/address/jurisdiction, official security contact, support identity,
commercial approval, package migration identity and production authority remain
owner inputs. Domain/DNS/TLS/edge headers/cache, origin protection and real
rollback are future infrastructure evidence. These are not silently converted
into engineering defects or marked completed.

Current installation remains `rai-governance-platform`; `responsibleai` is an
implementation namespace. No unverified replacement package is advertised.
The package inventory is a review aid, not authority to rename packages.

No deployment, DNS, Cloudflare, Hetzner, R2, GCP, billing activation, PyPI/GHCR
publication or production mutation is performed. A draft PR and green CI do
not authorize any of those actions. Antigravity owns independent qualification.
