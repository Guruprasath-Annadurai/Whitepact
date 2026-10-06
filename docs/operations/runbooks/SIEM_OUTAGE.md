# SIEM / observability outage

**Trigger:** SIEM collector down, export backlog, or tracing exporter failure.

1. **Contain:** none required for authority — governance continues fail-closed.
2. **Verify:** `SiemEventForwarder` reports `delivered=False` without crashing (`test_m4_chaos_fail_closed.py`); OTEL no-op safe (`test_m4_telemetry_fail_closed.py`).
3. **Recover:** drain audit export backlog after collector returns; do not replay consequential actions.
4. **Evidence:** local audit chain integrity via `AuditRepository.verify_chain`.
5. **Escalate:** if audit DB write fails, treat as `DATABASE_OUTAGE.md`.
