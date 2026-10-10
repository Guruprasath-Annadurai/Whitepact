# Phase 4 — staging acceptance checklist

**Status: NOT ACCEPTED. Nothing in this checklist was executed against a live staging system.**

Owner approval is still required before provisioning. `terraform apply`, DNS changes, and `scripts/deploy.sh` were not run.

| Step | Offline preparation | Live result |
|------|---------------------|-------------|
| Exact SHA and tree recorded | Required at deploy time | Not deployed |
| GitHub CI green on that SHA | See the PR #171 record. A later commit needs its own run | Not a staging pass |
| Antigravity written result for that same SHA | Phase 2 pass is `996795a` only | Not granted for `6801d4ad` |
| `terraform validate` on staging | Run in the Phase 3 preflight | Not a plan or apply |
| `terraform plan` read | `scripts/cloud/staging-preapply-verify.sh` checks a plan JSON | No plan file produced |
| Secrets present outside git | Hetzner token, Cloudflare token, SSH key `whitepact-staging-admin`, admin CIDRs | Not loaded |
| Image digest pinned | `Dockerfile` runtime stage pins `python:3.12-slim@sha256` | Image not deployed |
| Database migrations | `migrations/` and `scripts/deploy.sh --migrate-only` exist for compose | Not applied on staging |
| Health check | Dockerfile `HEALTHCHECK` hits `/api/health` | No host answered |
| MCP authorize path | Hosted MCP requires tenant governance and `_whitepact_purpose` | Not called on a live server |
| MCP deny path | Missing governance returns `governance_unavailable`. Enterprise stdio exits 2 | Unit tests only |
| Backup and restore | `scripts/cloud/gate2/backup_restore_dry_run.sh` | No live object written |
| Rollback | Redeploy previous pinned SHA, or destroy staging, under a new approval | Nothing to roll back |

Do not mark a row live-passed from this document.
