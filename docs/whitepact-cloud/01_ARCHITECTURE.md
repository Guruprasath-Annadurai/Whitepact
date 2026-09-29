# WhitePact Cloud — Architecture

## Doctrine

Production administration must follow the same rule as agent execution: **think freely, act only within enforced authority.**

## Separation

| Plane | Purpose | Exposure |
|-------|---------|----------|
| Public WhitePact SaaS | Customer governance API/MCP | Cloudflare → LB → private SaaS tier |
| WhitePact Cloud | Employee identity, JIT admin grants, audit | Cloudflare Access + Tunnel (no direct public admin ports) |
| Authority tier | Policy DB, signing, governance engine | Private network only |
| Execution tier | Isolated agent workloads | Private; egress allowlist only |

WhitePact Cloud uses **separate service identities and signing keys** from production authorization signing material (`src/responsibleai/whitepact_cloud/` vs `governance/`).

## Recovery independence

Emergency owner credentials and provider-native break-glass paths are documented in `04_PRIVILEGED_ACCESS.md` and `10_DISASTER_RECOVERY.md`. WhitePact Cloud outage must not be the only recovery path.

## Status

| Component | Status |
|-----------|--------|
| IaC topology (Hetzner module) | IMPLEMENTED_NOT_DEPLOYED |
| Admin grant library | VERIFIED (unit tests) |
| Cloudflare Access/Tunnel | OWNER_APPROVAL_REQUIRED (apply) |
| Live staging qualification | BLOCKED (no billable apply) |
