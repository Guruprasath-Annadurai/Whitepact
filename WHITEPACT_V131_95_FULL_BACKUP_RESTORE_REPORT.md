# Full backup / restore (Phase 0B)

**Verdict:** **PASS** (destroy + restore + manifest match)

**Population depth:** **PARTIAL** — seed includes orgs/users/memberships; evidence/approvals/billing not fully populated in this harness (see `test_historical_postgres_migrations.py` for richer migration preservation proofs).

Dump size: 305144 bytes

## Pre manifest

```json
{
  "orgs": [
    "org_br_alpha",
    "org_br_beta"
  ],
  "users": [
    "u_br_1"
  ],
  "table_counts": {
    "organizations": 2,
    "web_users": 1,
    "web_memberships": 1,
    "org_api_keys": 0,
    "governance_evidence": 0,
    "governance_policies": 0,
    "governance_approvals": 0,
    "governance_execution_nonces": 0,
    "audit_log": 0
  },
  "alembic_version": "0061"
}
```

## Post manifest

```json
{
  "table_counts": {
    "organizations": 2,
    "web_users": 1,
    "web_memberships": 1,
    "org_api_keys": 0,
    "governance_evidence": 0,
    "governance_policies": 0,
    "governance_approvals": 0,
    "governance_execution_nonces": 0,
    "audit_log": 0
  },
  "alembic_version": "0061"
}
```
