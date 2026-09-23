<!--
Copyright (c) 2026 Guruprasath Annadurai
SPDX-License-Identifier: MIT
-->

# WhitePact Enterprise Phase 5: Policy Lifecycle, Data Governance & Tenant Erasure
## Architecture & Subsystem Design Specification

**Document:** `docs/superpowers/specs/2026-09-12-policy-data-governance-design.md`  
**Status:** APPROVED FOR IMPLEMENTATION  
**Target Branch:** `feature/policy-data-governance-phase5`  
**Parent Phase-4 SHA:** `8c7534975d63ee7b752f96d974baf2239b31573b`  

---

### Executive Summary

Phase 3 established the Global Trust Fabric (principal identity, organizational boundaries, authority delegation). Phase 4 established Enterprise IAM and Privileged Administration (step-up authentication, JIT grants, four-eyes authorization, break-glass emergencies, and sovereign root recovery).

Phase 5 establishes the authoritative **Enterprise Policy Lifecycle and Data Governance Control Plane**. It resolves:
1. **Policy Lifecycle & Historical Integrity (5A)**: Monotonically numbered, immutable policy revisions; deterministic canonical content digests; atomic single-winner activation with row-level locking; safe rollback without history deletion; policy-to-evidence cryptographic binding; and TOCTOU prevention during multi-step governance flows.
2. **Data Inventory & Classification (5B)**: Authoritative classification of all 51+ database tables, runtime caches, and ephemeral stores into structured sensitivity categories (`PUBLIC`, `TENANT_OPERATIONAL`, `PERSONAL`, `SENSITIVE_SECURITY`, `CREDENTIAL_SECRET`, `CANONICAL_SECURITY_EVIDENCE`, `DERIVED_CACHE`, `SYSTEM_METADATA`).
3. **Retention, Export, Erasure & Legal Hold (5C)**: Automated retention policy evaluation; structured tenant export bundles with manifest and secret redaction; a strict, verifiable erasure state machine that eliminates false completion acknowledgments; and category-scoped legal holds that block deletion without retaining unrelated data.
4. **Tenant Deletion Orchestrator (5D)**: Multi-step governed workflow enforcing administrative privilege, immediate tenant quarantine, immediate credential and authority revocation, dependency-ordered data erasure, cache invalidation, durable tenant tombstoning with unique generation IDs, and independent post-deletion residual row scanning.
5. **Backup Resurrection Defense (5E)**: Persistent tombstone ledger, restore quarantine enforcement, and post-restore reconciliation preventing the resurrection of erased data, revoked sessions, or deleted authority after database snapshot restoration.

---

### 1. Architectural Approaches Evaluated

#### Approach A: Soft-Delete Column Flags on Existing Tables
*Concept:* Add `is_deleted` and `deleted_at` booleans to existing tables.
- *Pros:* Minimal schema disruption; simple queries.
- *Cons:* Fails data privacy requirements (data is not erased, only hidden); creates silent data leakage risks if queries omit the filter; does not resolve foreign key RESTRICT constraints on immutable evidence; vulnerable to resurrection attacks on tenant ID reuse.
- *Verdict:* REJECTED.

#### Approach B: Ad-Hoc Scripted Deletion per Service
*Concept:* Each domain service implements its own deletion and retention cleanup routines called sequentially by the API endpoint.
- *Pros:* Decentralized code changes.
- *Cons:* Lacks centralized transaction boundary; susceptible to partial failure leaving orphaned data; cannot guarantee fail-closed verification or tombstone ledger consistency; impossible to guarantee zero false erasure acknowledgments.
- *Verdict:* REJECTED.

#### Approach C: Governed State Machine Orchestrator with Immutable Revisions & Tombstone Ledger (Selected)
*Concept:*
- Distinct immutable tables for policy revisions (`governance_policy_revisions`) and activations (`governance_policy_activations`) with row-level locks on activation.
- Dedicated data governance subsystem (`src/responsibleai/data_governance/`) containing modular, single-responsibility services for inventory, retention, export, erasure, legal hold, tenant deletion orchestration, and backup resurrection defense.
- Durable tombstone ledger with generational tenant scoping.
- Mandatory post-deletion verification scanner ensuring zero residual eligible rows before declaring success.
- *Verdict:* SELECTED.

---

### 2. Core Subsystems & Technical Invariants

#### 2.1 Policy Lifecycle Architecture (5A)
- **Immutable Revisions (`governance_policy_revisions`)**:
  Every change to an organization's policy produces a new, immutable row with `revision_num = max(existing) + 1`. In-place modification of existing revision rows is prohibited at both application and database levels.
- **Canonical Content Digest**:
  Deterministic SHA-256 computed over canonical JSON representation of normalized rules:
  31884\text{digest} = \text{SHA256}(\text{JSON}(\text{sort\_keys=True, separators=(',', ':')}))31884
  Rules are sorted by position, and internal set fields (`action_types`, `risk_tiers`, `targets`) are alphabetically sorted.
- **Atomic Activation (`governance_policy_activations`)**:
  Only one active revision exists per organization (`is_active = True`). Activation uses PostgreSQL row locking (`SELECT FOR UPDATE`) to eliminate concurrent activation races. Activating a revision atomically bumps the organization's governance epoch, invalidating in-flight cached authorizations.
- **Safe Rollback**:
  Rolling back to a previous revision $ creates a *new activation* pointing to $ (or creates revision {n+1}$ identical to $). Historical revisions  \dots R_n$ and activation logs remain strictly immutable and preserved for audit.
- **Policy TOCTOU & Evidence Binding**:
  Execution authorizations and canonical evidence bundles record both `policy_version` and `policy_digest`. If the active policy digest changes between authorization and execution, execution is rejected as stale (`POLICY_STALE`).

#### 2.2 Data Inventory & Classification (5B)
Every PostgreSQL table and persistent structure is classified into an authoritative matrix:
1. `PUBLIC`: Benchmark results, system incident summaries.
2. `TENANT_OPERATIONAL`: Tool configs, evaluation runs, performance metrics.
3. `PERSONAL`: Web identities, active web sessions, SCIM user profiles.
4. `SENSITIVE_SECURITY`: Lineage keys, JIT grants, four-eyes requests, OAuth tokens.
5. `CREDENTIAL_SECRET`: Private keys, secret hashes, symmetric master keys.
6. `CANONICAL_SECURITY_EVIDENCE`: Governance evidence chains, root authority records, consent proofs, immutable audit logs.
7. `DERIVED_CACHE`: In-memory rate-limiter buckets, session caches, routing caches.
8. `SYSTEM_METADATA`: Alembic migration version, global platform configuration.

#### 2.3 Retention & Legal Hold (5C)
- **Retention Engine**:
  Idempotent batch processing evaluated against `data_retention_policies`. Prunes expired tenant operational records without touching held data or canonical evidence.
- **Legal Hold Engine**:
  Holds are scoped by `org_id` and specific `data_category`. An active hold suspends erasure for matching categories while permitting erasure of unheld operational categories. Holds require Phase-4 Privileged Surface Guard authorization (`PRIVILEGED_HIGH`).

#### 2.4 Structured Data Export (5C)
- Produces a deterministic archive/bundle containing a cryptographic manifest:
  - `export_id`, `org_id`, `created_at`, `record_counts`, `content_digest`.
- **Zero-Secret Export**: Automatically filters out all fields and tables classified as `CREDENTIAL_SECRET` (symmetric keys, private keys, password hashes).

#### 2.5 Tenant Erasure & Deletion Orchestration (5D)
- Orchestrated workflow:
  1. Verify privileged authorization (`PRIVILEGED_CRITICAL` via Sovereign Root or Four-Eyes).
  2. Evaluate legal holds.
  3. Enter `QUARANTINED` state (blocks all inbound execution and admin traffic).
  4. Immediately revoke all sessions, API keys, SCIM tokens, and JIT grants.
  5. Delete eligible personal, operational, and sensitive security data in topological dependency order.
  6. Invalidate derived caches.
  7. Register durable tombstone in `tenant_tombstones` with unique `generation_id`.
  8. Execute post-deletion verification scanner across all 51 tables.
  9. Record canonical lifecycle evidence.

#### 2.6 Backup Resurrection Defense (5E)
- **Tombstone Ledger (`tenant_tombstones`)**:
  Maintains permanent records of deleted organizations and their generation IDs.
- **Restore Quarantine Guard**:
  Following database restore from backup/snapshot, the restore reconciler cross-checks all restored organizations and credentials against the tombstone ledger. Any entity marked as tombstoned prior to restore is forced into quarantine, preventing resurrection of deleted authority or expired sessions.

---

### 3. Verification & Acceptance Criteria
- 17 dedicated Phase-5 test suites passing with 100% assertion coverage.
- Full regression suite passing across Phase 1, Phase 2, Phase 3, and Phase 4.
- Zero open P0/P1 security findings.
- Zero static analysis violations (`ruff`, `mypy`, `manage_license_headers.py`, `gitleaks`).
