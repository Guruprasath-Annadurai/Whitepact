# Database outage

**Trigger:** PostgreSQL unavailable, migration failure, or connection pool exhaustion.

1. **Contain:** stop workers that claim leases; surface 503 on dashboard/MCP admission paths (fail closed).
2. **Verify:** no partial execution marked `EXECUTED`; check outbox/attempt tables for `UNKNOWN` outcomes.
3. **Recover:** restore from last verified backup per `RESTORE_VERIFICATION.md` (test env only until founder approves prod).
4. **Evidence:** log outage window; reconcile SIEM delivery backlog after recovery.
5. **Escalate:** if data corruption suspected, halt all governance mutations until integrity checks pass.
