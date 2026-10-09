# Cloud staging — Antigravity handoff

**Status:** `CLOUD_STAGING_PLAN_COMPLETE — AWAITING_OWNER_GATE_1`  
**M6 qualified SHA:** `ee6e4a26becf7e89a933202651fba3b4e7a8176d`

## Package index

| Document | Purpose |
|----------|---------|
| `CLOUD_STAGING_COST_AND_RESOURCE_PLAN.md` | Owner Gate 1 |
| `CLOUD_STAGING_TOPOLOGY.md` | Topologies A/B |
| `CLOUD_NETWORK_TRUST_BOUNDARY.md` | Trust zones |
| `CLOUD_ORIGIN_PROTECTION.md` | ORIGIN-LIVE-BYPASS plan |
| `CLOUD_SECRET_INVENTORY.md` | Secret types |
| `CLOUD_BACKUP_AND_RESTORE_EVIDENCE.md` | Backup/restore criteria |
| `CLOUD_OBSERVABILITY_AND_ALERTING.md` | Logs/metrics/alerts |
| `CLOUD_DEPLOYMENT_EVIDENCE.md` | Audit + live evidence slots |
| `CLOUD_STAGING_KNOWN_LIMITATIONS.md` | Honest limits |

## IaC

- `infra/terraform/environments/staging/`
- Module: `whitepact-hetzner-foundation` (`environment=staging` → 1× SaaS, 1× authority, 1× execution)

## Cursor claim boundary

Cursor may **not** claim `CLOUD PASS` or `CLOUD_STAGING_ENGINEERING_COMPLETE` until live evidence sections in `CLOUD_DEPLOYMENT_EVIDENCE.md` are filled and Antigravity qualifies.

After provisioning + drills, target status:

> **CLOUD_STAGING_ENGINEERING_COMPLETE — READY_FOR_ANTIGRAVITY**
