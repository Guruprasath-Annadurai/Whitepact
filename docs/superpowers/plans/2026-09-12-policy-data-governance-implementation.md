<!--
Copyright (c) 2026 Guruprasath Annadurai
SPDX-License-Identifier: MIT
-->

# WhitePact Enterprise Phase 5: Policy Lifecycle, Data Governance & Tenant Erasure
## Superpowers Implementation Plan

**Document:** `docs/superpowers/plans/2026-09-12-policy-data-governance-implementation.md`  
**Status:** READY TO EXECUTE  
**Target Branch:** `feature/policy-data-governance-phase5`  
**Parent Phase-4 SHA:** `8c7534975d63ee7b752f96d974baf2239b31573b`  

---

### Implementation Milestones & Task Breakdown

#### Milestone 1: Baseline Reproduction & Data Inventory Documentation
- [ ] Create `docs/security/PHASE5_POLICY_BASELINE_REPRODUCTION.md` detailing policy revision and concurrency baselines.
- [ ] Create `docs/security/PHASE5_DATA_LIFECYCLE_BASELINE_REPRODUCTION.md` detailing data erasure, FK RESTRICT, and resurrection baselines.
- [ ] Create `docs/security/PHASE5_DATA_INVENTORY.md` documenting all 51+ tables, data classifications, retention periods, and erasure behaviors.

#### Milestone 2: Database Migration 0045 & Schema Engine Updates
- [ ] Update `src/responsibleai/db/engine.py`:
  - Define `governance_policy_revisions`
  - Define `governance_policy_activations`
  - Define `data_retention_policies`
  - Define `data_lifecycle_requests`
  - Define `data_holds`
  - Define `tenant_tombstones`
  - Define `restore_reconciliation_records`
- [ ] Create `migrations/versions/0045_policy_lifecycle_data_governance.py` with `down_revision = '0044'`.
- [ ] Verify clean forward and reverse migration on SQLite and PostgreSQL.

#### Milestone 3: Subsystem 5A — Policy Lifecycle, Canonical Digest & Atomic Activation
- [ ] Implement `src/responsibleai/governance/policy_lifecycle.py`:
  - `PolicyRevisionManager`: Monotonic revision numbering, canonical SHA-256 rule digest calculation.
  - `PolicyActivationManager`: Atomic activation with row-level locking, governance epoch increment.
  - `PolicyRollbackManager`: Safe rollback creating new activations without rewriting history.
  - `PolicyGuardIntegrator`: Integration with Phase-4 PrivilegedSurfaceGuard for step-up and four-eyes enforcement.
- [ ] Create tests:
  - `tests/test_policy_revision_history.py`
  - `tests/test_policy_activation.py`
  - `tests/test_policy_rollback.py`
  - `tests/test_policy_concurrency.py`
  - `tests/test_policy_evidence_binding.py`
  - `tests/test_policy_privileged_governance.py`

#### Milestone 4: Subsystem 5B & 5C — Data Classification, Retention, Export, Erasure & Legal Hold
- [ ] Implement `src/responsibleai/data_governance/classification.py` & `inventory.py`:
  - Authoritative classification matrix and schema introspection.
- [ ] Implement `src/responsibleai/data_governance/retention.py`:
  - Batch retention pruner evaluating against retention policies.
- [ ] Implement `src/responsibleai/data_governance/export.py`:
  - Manifest-backed structured export excluding secrets.
- [ ] Implement `src/responsibleai/data_governance/legal_hold.py`:
  - Category-scoped legal hold management with privileged access controls.
- [ ] Implement `src/responsibleai/data_governance/erasure.py`:
  - Verified erasure state machine (`REQUESTED` -> `VALIDATED` -> `IN_PROGRESS` -> `COMPLETED` / `FAILED`).
- [ ] Create tests:
  - `tests/test_data_inventory.py`
  - `tests/test_retention_lifecycle.py`
  - `tests/test_data_export.py`
  - `tests/test_erasure.py`
  - `tests/test_legal_hold.py`

#### Milestone 5: Subsystem 5D & 5E — Tenant Deletion Orchestration & Backup Resurrection Defense
- [ ] Implement `src/responsibleai/data_governance/deletion_orchestrator.py`:
  - Quarantine enforcement, credential revocation, cascade erasure, cache purge, tombstoning, and post-deletion scan.
- [ ] Implement `src/responsibleai/data_governance/backup_defense.py`:
  - Restore quarantine guard and tombstone reconciliation.
- [ ] Create tests:
  - `tests/test_tenant_deletion.py`
  - `tests/test_backup_resurrection.py`
  - `tests/test_restore_reconciliation.py`
  - `tests/test_phase5_tenant_isolation.py`
  - `tests/test_phase5_postgres_concurrency.py`
  - `tests/test_phase5_migrations.py`

#### Milestone 6: Quality Gates, Static Analysis & Full Regression
- [ ] Run `ruff check src tests`.
- [ ] Run `mypy src/responsibleai/`.
- [ ] Verify copyright & SPDX headers using `python scripts/manage_license_headers.py --check`.
- [ ] Ensure `git diff --check` passes cleanly.
- [ ] Run `gitleaks dir --verbose` and `gitleaks git --verbose`.
- [ ] Run full test suite regression across all phases.
- [ ] Produce `docs/security/PHASE5_POLICY_DATA_GOVERNANCE_CLOSURE.md`.
