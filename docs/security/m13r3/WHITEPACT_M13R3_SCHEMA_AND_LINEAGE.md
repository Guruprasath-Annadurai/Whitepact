# WHITEPACT M13-R3 SCHEMA AND LINEAGE

**Milestone:** M13-R3  
**Subject:** Alembic Migration Consolidation, Schema Definition, and Integrity  
**Status:** CONSOLIDATED & PROVEN

---

## 1. Migration Lineage Consolidation

Prior branches suffered from diverging Alembic migration heads at revision `0064` (one creating partial recovery tables, another creating containment records with conflicting string lengths).

In M13-R3, migration `0064_authority_containment_and_recovery.py` consolidates all required security tables into a single linear chain:

```text
0062_governance_consent_root_bridge
  └── 0063_governance_revocation_epochs
        └── 0064_authority_containment_and_recovery
```

Downstream and upstream compatibility is preserved without manual resolution flags or diverging revisions.

---

## 2. Security Table Specifications

Migration `0064` defines the following authority and recovery tables:

### 1. `authority_step_up_challenges`
Tracks short-lived, phishing-resistant WebAuthn challenges and Path B pre-verified tickets.
- `challenge_hash`: `VARCHAR(64)` PRIMARY KEY (SHA-256 of challenge).
- `org_id`: `VARCHAR(64)` FOREIGN KEY -> `organizations.id` ON DELETE CASCADE.
- `user_id`: `VARCHAR(64)` FOREIGN KEY -> `web_users.id` ON DELETE CASCADE.
- `session_id`: `VARCHAR(64)` NULLABLE.
- `action`: `VARCHAR(64)` NOT NULL.
- `operation_digest`: `VARCHAR(64)` NOT NULL.
- `rp_id`: `VARCHAR(255)` NOT NULL.
- `origin`: `VARCHAR(512)` NOT NULL.
- `raw_challenge_b64`: `TEXT` NOT NULL.
- `created_at`: `VARCHAR(32)` NOT NULL.
- `expires_at`: `VARCHAR(32)` NOT NULL.
- `consumed_at`: `VARCHAR(32)` NULLABLE.
- Constraints: Index on `idx_stepup_org_user`, index on `idx_stepup_consumed`.

### 2. `authority_containment_records`
Persistent record of emergency containment actions, admission locks, and termination status.
- `id`: `VARCHAR(64)` PRIMARY KEY.
- `org_id`: `VARCHAR(64)` FOREIGN KEY -> `organizations.id` ON DELETE CASCADE.
- `responder_user_id`: `VARCHAR(64)` FOREIGN KEY -> `web_users.id` ON DELETE SET NULL.
- `target_type`: `VARCHAR(32)` NOT NULL.
- `target_id`: `VARCHAR(64)` NOT NULL.
- `containment_action`: `VARCHAR(32)` NOT NULL.
- `reason`: `TEXT` NOT NULL.
- `status`: `VARCHAR(32)` NOT NULL (`TERMINATION_PENDING`, `CONTAINED`, `UNRESOLVED`).
- `revocation_epoch`: `INTEGER` NOT NULL.
- `contained_at`: `VARCHAR(32)` NOT NULL.
- Constraints: Index on `idx_containment_org`, index on `idx_containment_status`.

### 3. `authority_recovery_requests`
Multi-approver M-of-N sovereign recovery tracking.
- `id`: `VARCHAR(64)` PRIMARY KEY.
- `org_id`: `VARCHAR(64)` FOREIGN KEY -> `organizations.id` ON DELETE CASCADE.
- `target_root_id`: `VARCHAR(64)` NULLABLE.
- `requester_user_id`: `VARCHAR(64)` FOREIGN KEY -> `web_users.id` ON DELETE CASCADE.
- `request_type`: `VARCHAR(64)` NOT NULL.
- `proposed_parameters_json`: `TEXT` NOT NULL.
- `action_digest`: `VARCHAR(64)` NOT NULL.
- `required_quorum_m`: `INTEGER` NOT NULL.
- `eligible_quorum_n`: `INTEGER` NOT NULL.
- `status`: `VARCHAR(32)` NOT NULL (`PENDING`, `APPROVED`, `EXECUTED`, `EXPIRED`, `REJECTED`).
- `created_at`: `VARCHAR(32)` NOT NULL.
- `expires_at`: `VARCHAR(32)` NOT NULL.
- `executed_at`: `VARCHAR(32)` NULLABLE.
- `executed_by_user_id`: `VARCHAR(64)` NULLABLE.

### 4. `authority_recovery_votes`
Individual administrator quorum votes.
- `id`: `VARCHAR(64)` PRIMARY KEY.
- `request_id`: `VARCHAR(64)` FOREIGN KEY -> `authority_recovery_requests.id` ON DELETE CASCADE.
- `voter_user_id`: `VARCHAR(64)` FOREIGN KEY -> `web_users.id` ON DELETE CASCADE.
- `decision`: `VARCHAR(16)` NOT NULL (`APPROVE`, `REJECT`).
- `notes`: `TEXT` NOT NULL.
- `voted_at`: `VARCHAR(32)` NOT NULL.
- Constraints: `UniqueConstraint("request_id", "voter_user_id", name="uq_recovery_vote_request_voter")`.

---

## 3. Migration Roundtrip & ID Length Verification

The migration was verified using Codex's independent migration roundtrip suite:

```bash
.venv/bin/pytest tests/independent_m13r2/test_m13r_migration_roundtrip.py tests/independent_m13r2/test_m13p_postgres_schema.py -o addopts="" -v
```

**Results:**
- `test_0063_upgrade_0064_constraints_and_safe_empty_downgrade`: **PASSED**
  (Verified full upgrade from 0063 to 0064, table creation, and safe clean downgrade back to 0063).
- `test_migration_accepts_runtime_generated_identifier_lengths`: **PASSED**
  (Verified that runtime IDs up to 64 characters such as `wp_cnt_<uuid>`, `wp_authz_<uuid>`, `wp_rec_<uuid>` fit without truncation).
- `test_fresh_migrations_supply_security_contract_tables`: **PASSED**
  (Verified PostgreSQL schema compliance on a freshly migrated database).
