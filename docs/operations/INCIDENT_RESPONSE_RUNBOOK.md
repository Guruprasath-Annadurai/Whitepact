# Incident Response Runbook

## Lifecycle

DETECT → TRIAGE → CONTAIN → MITIGATE → RECOVER → VERIFY → COMMUNICATE → POSTMORTEM → REMEDIATE

## Triage checklist

1. Severity (see severity model below)
2. Affected tenants / blast radius
3. Deployment SHA (`/api/health` version field)
4. Restore gate status (`/api/restore/status`)
5. Preserve logs and audit exports

## Containment (authority-safe)

- Prefer **fail closed** (deny new consequential execution) over open mode.
- Use maintenance / restore gate rather than disabling auth globally.

## Severity

| Level | Example |
|-------|---------|
| SEV0 | Authority bypass, key compromise, cross-tenant data |
| SEV1 | Full outage, data loss risk |
| SEV2 | Partial degradation |
| SEV3 | Minor defect |

## What NOT to do

- Do not disable governance to restore green dashboards
- Do not delete audit tables during incident cleanup
- Do not restore backups without reconciliation

See `SECURITY_INCIDENT_RUNBOOK.md` for credential compromise.
