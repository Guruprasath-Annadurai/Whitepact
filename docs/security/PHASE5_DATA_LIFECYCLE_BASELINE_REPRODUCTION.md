<!--
Copyright (c) 2026 Guruprasath Annadurai
SPDX-License-Identifier: MIT
-->

# WhitePact Phase 5: Data Lifecycle & Tenant Erasure Baseline Reproduction

**Document:** `docs/security/PHASE5_DATA_LIFECYCLE_BASELINE_REPRODUCTION.md`  
**Baseline SHA:** `8c7534975d63ee7b752f96d974baf2239b31573b`  
**Target Branch:** `feature/policy-data-governance-phase5`  

---

## 1. Executive Summary

This document details the baseline data lifecycle, tenant deletion, foreign-key constraints, and resurrection vulnerabilities identified in WhitePact prior to Phase 5.

---

## 2. Pre-Phase-5 Deficiencies Identified

1. **Foreign Key RESTRICT Blocks Tenant Deletion**:
   - 9 tables in the schema (`governance_evidence`, `governance_evidence_chain_heads`, `governance_root_authority_records`, `governance_consent_proofs`, etc.) are configured with `ON DELETE RESTRICT` on `organizations.id`.
   - Any attempt to delete an active organization with historical evidence caused an unhandled `IntegrityError` aborting the transaction.
2. **Silent Orphan Residue in 27+ Unconstrained Tables**:
   - 27 tables lack foreign keys referencing `organizations.id`.
   - Deleting an organization row left orphaned data across API keys, policies, webhooks, audit logs, and tool trust scores.
3. **Tenant ID Reuse & Authority Resurrection**:
   - Recreating an organization with the same identifier or slug re-attached to all orphaned API keys, policies, and privileges.
4. **False Erasure Acknowledgement**:
   - Deletion APIs returned HTTP 200/204 before data was actually purged, or returned success while RESTRICT constraints silently blocked complete erasure.
5. **Backup Resurrection Vulnerability**:
   - Restoring a PostgreSQL database dump restored all deleted tenants and credentials without detecting prior erasure or tombstoning.
6. **Absence of Structured Data Export & Legal Hold**:
   - No mechanism existed to export complete tenant data bundles or place legal holds preventing erasure.

---

## 3. Phase 5 Canonical Solution

1. **Tenant Deletion Orchestrator**:
   - Governed multi-step workflow: Privileged check -> Legal Hold evaluation -> Quarantine -> Revoke credentials & sessions -> Dependency-ordered data erasure -> Cache invalidation -> Tombstoning with unique Generation ID -> Post-deletion verification.
2. **Generational Scoping**:
   - Prevents tenant resurrection by binding authority and credentials to a specific `generation_id`. Recreating a tenant assigns a new generation, rendering prior orphaned records inaccessible.
3. **Verified Erasure State Machine**:
   - Explicit states: `REQUESTED` -> `VALIDATED` -> `IN_PROGRESS` -> `COMPLETED` / `FAILED`.
   - Success is acknowledged ONLY after the post-deletion scanner confirms 0 residual eligible rows.
4. **Backup Resurrection Defense**:
   - Restores are checked against a persistent tombstone ledger. Restored deleted tenants are immediately quarantined and their credentials invalidated.
5. **Legal Hold Engine**:
   - Scoped by organization and data category, preventing accidental deletion of legally preserved data while allowing erasure of unheld operational data.
