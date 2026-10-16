# WHITEPACT M13-S4 POSTGRESQL MIGRATION INTEGRITY & SCHEMA LINEAGE

**Milestone:** M13-S4 — Priority E Enforcement  
**Security Owner:** Antigravity — Principal Security & Reliability Engineer  
**Canonical Alembic Head:** Revision `0064_authority_recovery_schema`  
**Target Engine:** PostgreSQL 16+ / 17 (Enterprise ACID Compliant)  
**Status:** **MIGRATION LINEAGE PROVEN & SCHEMA COMPATIBILITY VERIFIED**

---

## 1. Canonical Migration Chain Analysis

WhitePact strictly prohibits runtime DDL creation or test-fixture schema alterations. All database tables, indexes, unique constraints, and foreign key relationships must be declared through tracked, versioned Alembic migration scripts.

### Recent Migration History

| Revision ID | Name / Description | Down Revision | Tables Introduced / Altered |
| :--- | :--- | :--- | :--- |
| `0062` | `trust_fabric_bootstrap_records` | `0061` | Root bootstrap ceremony records |
| `0063` | `passkey_stepup_and_containment` | `0062` | `authority_step_up_challenges`, `authority_containment_records` |
| `0064` | `authority_recovery_schema` | `0063` | `authority_recovery_requests`, `authority_recovery_votes`, identifier length extensions |

---

## 2. Table Schemas, Constraints & Identifier Lengths

### 1. `authority_containment_records`
- `id VARCHAR(64) PRIMARY KEY`: Accommodates runtime generated prefixed UUIDs (`wp_cnt_<uuid4_hex>`, 39 chars, comfortably below 64).
- `org_id VARCHAR(64) NOT NULL REFERENCES organizations(org_id)`: Multi-tenant tenant boundary foreign key.
- `target_type VARCHAR(32) NOT NULL`: Enum values (`AGENT`, `ORGANIZATION`, `WORKER`, `EXECUTION`).
- `target_id VARCHAR(64) NOT NULL`: Target identifier.
- `containment_action VARCHAR(32) NOT NULL`: Enum values (`QUARANTINE`, `LOCKDOWN`, `TERMINATE`, `REVOKE`).
- `status VARCHAR(32) NOT NULL`: State machine (`TERMINATION_PENDING`, `CONTAINED`, `PARTIALLY_FAILED`, `UNRESOLVED`).
- `revocation_epoch INTEGER NOT NULL DEFAULT 1`: Tenant revocation epoch increment.
- `contained_at VARCHAR(64)`: Timestamp of physical containment.
- `created_at VARCHAR(64) NOT NULL`: Timestamp of initial durable commitment.

### 2. `authority_recovery_requests`
- `id VARCHAR(64) PRIMARY KEY`: Accommodates `wp_recov_<uuid4_hex>`.
- `org_id VARCHAR(64) NOT NULL REFERENCES organizations(org_id)`: Tenant isolation foreign key.
- `request_type VARCHAR(32) NOT NULL`: Recovery action type (`ROOT_RECOVERY`, `ORGANIZATION_UNFREEZE`).
- `requester_user_id VARCHAR(64) NOT NULL`: Admin initiating recovery.
- `proposed_parameters_json TEXT NOT NULL`: Canonical JSON representation of proposed recovery parameters.
- `action_digest VARCHAR(64) NOT NULL`: SHA-256 digest of proposed parameters.
- `status VARCHAR(32) NOT NULL DEFAULT 'PENDING'`: Status (`PENDING`, `EXECUTED`, `EXPIRED`, `CANCELLED`).
- `created_at VARCHAR(64) NOT NULL`: Request creation timestamp.
- `expires_at VARCHAR(64) NOT NULL`: Request expiration timestamp.

### 3. `authority_recovery_votes`
- `id VARCHAR(64) PRIMARY KEY`: Accommodates `wp_rvote_<uuid4_hex>`.
- `request_id VARCHAR(64) NOT NULL REFERENCES authority_recovery_requests(id) ON DELETE CASCADE`: Foreign key binding.
- `voter_user_id VARCHAR(64) NOT NULL`: Admin casting vote.
- `decision VARCHAR(16) NOT NULL`: Vote decision (`APPROVE`, `REJECT`).
- `action_digest VARCHAR(64) NOT NULL`: Cryptographic digest matching request.
- `voted_at VARCHAR(64) NOT NULL`: Voting timestamp.
- **Unique Constraint:** `UNIQUE(request_id, voter_user_id)`: Prevents multiple votes by the same administrator.

### 4. `authority_step_up_challenges`
- `id VARCHAR(64) PRIMARY KEY`: Challenge/ticket ID (`wp_step_<uuid4_hex>`).
- `org_id VARCHAR(64) NOT NULL REFERENCES organizations(org_id)`: Tenant binding.
- `user_id VARCHAR(64) NOT NULL`: Bound principal.
- `challenge_str VARCHAR(128) NOT NULL`: Base64URL-encoded cryptographic challenge.
- `operation_name VARCHAR(64) NOT NULL`: Scoped operation name.
- `action_digest VARCHAR(64) NOT NULL`: Bound operation parameters digest.
- `consumed BOOLEAN NOT NULL DEFAULT FALSE`: Atomic single-use flag.
- `consumed_at VARCHAR(64)`: Consumption timestamp.
- `consumed_by_actor_id VARCHAR(64)`: Actor consuming challenge.
- `expires_at VARCHAR(64) NOT NULL`: Bounded challenge expiration.

---

## 3. Fresh Installation & Roundtrip Downgrade Verification

To confirm schema reliability, the test suite executes complete migration cycles on fresh, isolated PostgreSQL databases:

```bash
# Upgrade from base (0000) to head (0064)
alembic upgrade head

# Downgrade from head (0064) to 0063
alembic downgrade 0063

# Re-upgrade to head (0064)
alembic upgrade head
```

- **Clean Upgrade:** Tables, indexes, and foreign keys are created without warnings or conflicts.
- **Safe Downgrade:** Reversion cleans up newly created tables without impacting predecessor relations.
- **No Undocumented Fixtures:** Codex's `test_m13p_postgres_schema.py` and `test_m13r_migration_roundtrip.py` verify that all required tables exist strictly via Alembic, not runtime `Base.metadata.create_all()` injections.

---

## 4. Test Evidence

- `tests/independent_m13r2/test_m13p_postgres_schema.py::test_fresh_migrations_supply_security_contract_tables` **PASSED**
- `tests/independent_m13r2/test_m13r_migration_roundtrip.py::test_0063_upgrade_0064_constraints_and_safe_empty_downgrade` **PASSED**
- `tests/independent_m13r2/test_m13r_migration_roundtrip.py::test_migration_accepts_runtime_generated_identifier_lengths` **PASSED**
- `tests/independent_m13r2/test_additional_readonly_probes.py::test_real_postgres_generated_ids_vote_uniqueness_and_rollback` **PASSED**
