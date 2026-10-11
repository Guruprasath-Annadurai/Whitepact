# Phase 4 — Staging acceptance tests

**Status: NOT EXECUTED against live infrastructure.**

Run this list only after an owner-authorized staging apply. A local pytest pass does not check these boxes.

| # | Test | Pass condition |
|---|------|----------------|
| 1 | Provenance | Deployed SHA equals the approved SHA and `git rev-parse HEAD^{tree}` |
| 2 | TLS | Cloudflare Full (strict) and origin certificate validate; HTTP does not serve the app |
| 3 | Origin pull | Request without authenticated origin pull is rejected |
| 4 | Authority isolation | SaaS cannot read the authority database connection string from the execution host |
| 5 | Worker isolation | Execution container has no host network and no docker socket |
| 6 | Grant deny | Tool call without a grant returns deny and writes an audit event |
| 7 | Grant allow | Fresh grant for the same tool returns allow once |
| 8 | Replay | Reuse of that grant returns deny |
| 9 | Expiry | A grant older than its TTL returns deny |
| 10 | Tenant | Org A token cannot read org B evidence |
| 11 | Memory scope | Delegated agent with a wider `memory_scope` is denied |
| 12 | Migration | Schema version matches the SHA's Alembic head |
| 13 | Health | Readiness fails when PostgreSQL is stopped and recovers when it returns |
| 14 | Backup | Encrypted backup object exists; key is not in the object store |
| 15 | Restore | Scratch restore row count and digest match |
| 16 | Rollback | Previous SHA becomes ready and the failed SHA stops receiving traffic |

Record each result with the UTC time, the SHA, and the operator. Store the record outside the git commit that is being deployed.

## Local substitutes already available

These do not replace the table:

- `python scripts/release_evidence_check.py docs/launch/evidence/rc-0cdef394.json` → `NO-GO`
- Governance slice described in `PHASE_02_ANTIGRAVITY_INDEPENDENT_AUDIT_HANDOFF.md`
- `terraform validate` on the staging root

## Gate

NOT EXECUTED.
