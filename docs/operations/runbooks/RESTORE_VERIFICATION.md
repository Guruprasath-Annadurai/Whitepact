# Restore verification (non-production)

**Trigger:** backup drill, disaster-recovery exercise, or pre-release restore gate.

1. **Contain:** use isolated PostgreSQL instance only; never restore production secrets into shared dev.
2. **Verify:** run migrations to head; compare org/policy/evidence counts; rerun `tests/test_restore_admission_chokepoint.py` smoke.
3. **Recover:** if schema mismatch, abort and fix backup pipeline — do not serve traffic from partial restore.
4. **Evidence:** record backup ID, restore timestamp, and hash/attestation checks where applicable.
5. **Escalate:** restore failure → mark `OPEN — BLOCKER` in M6 defect register until resolved.
