# Phase 0 — Supplemental engineering register (Cursor)

These items were identified during Phase 0 reconciliation. They are **not** Antigravity official BLK-* findings and **must not** be substituted in the master enterprise audit.

| ID | Sev | Title | Related BLK / CLOUD | Evidence | Verification |
|----|-----|-------|---------------------|----------|--------------|
| SUP-001 | P1 | Audit SHA `3c955c7` missing from `origin` | META | `PHASE0_BASELINE_RECONCILIATION.md` | **REPRODUCED** |
| SUP-002 | P1 | DNS egress / rebinding mitigation on `main` | (historical gate doc) | `src/responsibleai/net/egress.py`; `tests/test_dns_egress_security.py` | **VERIFIED_CLOSED** on B-main |
| SUP-003 | P0 | No single integrated enterprise RC SHA | BLK-P0-03, CLOUD-AG-06 | Open PRs #107, #108, #128 | **REPRODUCED** |
| SUP-004 | P0 | IoT / Device Bridge implementation absent | — | `docs/architecture/IOT_DEVICE_BRIDGE_HARDENING_AUDIT.md` | **REPRODUCED** |
| SUP-005 | P2 | `RELEASE_SECURITY_GATE.md` stale vs tests (epoch resume) | BLK-P0-04 class | Tests pass on B-main; doc still OPEN P0 | **CONTRADICTED_BY_EVIDENCE** (doc drift) |
| SUP-006 | P2 | Heart formal verification scope (property-only) | BLK-P0-03 | `HEART_ENTERPRISE_READINESS.md` | **REPRODUCED** |
| SUP-007 | P3 | Helm chart icon URL (WP-V131-FIND-004) | — | Enterprise hardening reports | **OPEN** |
