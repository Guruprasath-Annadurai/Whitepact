# Multicloud Access Governance

## Hetzner

- Separate **read** vs **provision** API tokens; provision tokens in secrets manager only.
- WhitePact Cloud cannot override an employee with unrestricted Hetzner project owner access.
- Audit: Hetzner activity log (account-level).

## Cloudflare

Scoped tokens per function: DNS, WAF/rules, Access admin, R2 backup, account admin.
Developers must not retrieve DNS-admin or backup-delete credentials.

## Google Cloud (optional)

- Least-privilege IAM; billing separated from engineering.
- Short-lived workload identity for CI where available.
- Production **must** operate when GCP credits expire.

## Emergency

Documented break-glass per provider; monitored and rare. See `09_INCIDENT_RESPONSE.md`.

## Status

| Provider | Design | Live IAM |
|----------|--------|----------|
| Hetzner | VERIFIED (docs + IaC) | OWNER_APPROVAL_REQUIRED |
| Cloudflare | VERIFIED | OWNER_APPROVAL_REQUIRED |
| GCP optional | VERIFIED | OWNER_APPROVAL_REQUIRED |
