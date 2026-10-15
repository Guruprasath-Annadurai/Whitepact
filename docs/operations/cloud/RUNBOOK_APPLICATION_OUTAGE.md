# Runbook — application outage (cloud staging/production)

**Trigger:** `/livez` or external monitor reports down; elevated 5xx.

**Contain:** Confirm scope (single host vs LB pool). Disable new executions if authority uncertain. Preserve logs.

**Verify:** LB health checks, container status, recent deploy SHA, Postgres `/readyz`.

**Recover:** Roll back to last known-good image digest; restart dashboard; verify `/readyz`.

**Evidence:** Incident ticket, deploy SHA, trace IDs, Antigravity evidence log entry.

**Escalate:** Founder + security if authority bypass suspected.
