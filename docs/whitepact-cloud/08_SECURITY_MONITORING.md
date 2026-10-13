# Security Monitoring

Initial affordable stack:

- WhitePact Cloud auth and grant events (structured audit)
- Hetzner / Cloudflare / GCP audit logs (where enabled)
- CI deployment and secret-access signals
- Backup operation logging

Alerts: failed auth bursts, new admin sessions/devices, privilege changes, backup deletion attempts, monitoring disable attempts.

**Status:** TESTED_IN_SIMULATION (event schema); live SIEM OWNER_APPROVAL_REQUIRED.
