# Rollback and Resource Cleanup

SHA: `caf539b`

## Application rollback (no destroy)

| Step | Action |
|------|--------|
| 1 | Disable CF Access application (stop ingress) |
| 2 | Set `PRIVILEGED_EXECUTOR_ENABLED=False` in deployment config |
| 3 | Deploy previous application image / wheel (if applicable) |
| 4 | `alembic downgrade` **only** if forward migration reversible and approved |

Status: **IMPLEMENTED** (procedure) — **AWAITING_LIVE_STAGING** execution

## Full staging teardown

| Order | Resource | Command / action | Verify |
|-------|----------|------------------|--------|
| 1 | Cloudflare Access app | Delete or disable in dashboard | URL 403 |
| 2 | DNS staging records | Remove A/CNAME to LB | `dig` empty |
| 3 | Hetzner LB | `terraform destroy` target LB | No listeners |
| 4 | Servers | destroy module | No servers in project |
| 5 | Network | destroy | No private nets |
| 6 | Volumes | delete if any | — |
| 7 | R2 objects | lifecycle delete staging prefix | bucket empty |
| 8 | API tokens | revoke Hetzner + CF staging tokens | API 401 |
| 9 | GitHub staging secrets | remove or rotate | — |

## Post-cleanup verification checklist

- [ ] Hetzner project shows **zero** servers and load balancers
- [ ] No staging DNS records pointing to Hetzner IPs
- [ ] R2 staging prefix has zero objects (or bucket deleted)
- [ ] CF Access policies for staging app removed
- [ ] Billing dashboard: note next invoice may include partial month
- [ ] Evidence archive moved to owner storage (optional)

## Maximum staging duration

Default **14 calendar days** from apply unless owner extends in writing.

## Items that may remain chargeable

- Cloudflare zone subscription (if production zone shared)
- R2 storage until purged
- Domain registration (unchanged)

## Emergency rollback during failed apply

1. `terraform destroy` (if partial apply)
2. Revoke leaked tokens immediately
3. Document incident in internal log — no secrets in git
