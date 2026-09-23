<!--
Copyright (c) 2026 Guruprasath Annadurai
SPDX-License-Identifier: MIT
-->

# WhitePact Phase 5: Policy Baseline Reproduction & Concurrency Audit

**Document:** `docs/security/PHASE5_POLICY_BASELINE_REPRODUCTION.md`  
**Baseline SHA:** `8c7534975d63ee7b752f96d974baf2239b31573b`  
**Target Branch:** `feature/policy-data-governance-phase5`  

---

## 1. Executive Summary

This document captures the empirical baseline analysis of WhitePact's pre-Phase-5 policy subsystem (`governance_policies` and `governance_policy_versions`), identifying the exact concurrency, integrity, and immutability deficiencies addressed in Phase 5.

---

## 2. Pre-Phase-5 Deficiencies Identified

1. **Mutable Policy Table (`governance_policies`)**:
   - Rules were modified in-place or deleted on mutation.
   - Deletion of a rule left no historical tombstone or record of what rule existed at a given timestamp.
2. **Scalar Version Counter (`governance_policy_versions`)**:
   - Only stored `(org_id, version, updated_at)`.
   - Lacked content snapshots, parent revision links, and cryptographic content hashes.
3. **Absence of Atomic Activation with Row Locking**:
   - Concurrent updates to policy rules could interleave updates without deterministic locking, risking inconsistent active rule sets.
4. **Lack of Policy-to-Evidence Cryptographic Binding**:
   - Decision evidence recorded `policy_version` (e.g., version 3) but lacked `policy_digest` (the exact SHA-256 hash of the rules).
   - If historical versions were mutable, proving what exact rules executed at version 3 was impossible.
5. **No Governed Rollback Mechanism**:
   - Reverting policy required manually re-inserting deleted rules, bumping version numbers without audit lineage.
6. **Policy / Execution TOCTOU Vulnerability**:
   - Multi-step authorization flows could evaluate against Policy V1, but by the time execution occurred, Policy V2 could have been activated without invalidating the authorization.

---

## 3. Phase 5 Canonical Solution

1. **Immutable Revisions Table (`governance_policy_revisions`)**:
   - Stores immutable snapshots: `(id, org_id, revision_num, rules_json, content_digest, created_at, created_by, change_reason, approval_id)`.
2. **Explicit Activation Table (`governance_policy_activations`)**:
   - Stores active state: `(id, org_id, revision_id, content_digest, activated_at, activated_by, governance_epoch, previous_activation_id, is_active)`.
   - Enforced by PostgreSQL row-level locks on activation.
3. **Deterministic Canonical Rule Digest**:
   - SHA-256 computed over sorted, canonical JSON rules.
4. **Epoch Invalidation**:
   - Every policy change atomically increments the organization's governance epoch, invalidating stale execution tokens.
5. **Privileged Surface Guard Integration**:
   - Policy mutations require Step-Up (HIGH) or Four-Eyes approval (CRITICAL) via Phase 4 IAM guard.
