# Phase 0 — Master defect register

**Classification:** Stage 1 — Development Only (consistent with Antigravity summary).  
**Rows:** 24 reconciled enterprise findings + 1 meta row.  
**Antigravity audit artifact:** Not present in-repo; row titles are reconciled from `RELEASE_SECURITY_GATE`, Heart readiness, Cloud pre-staging audit, IoT audit, and RC fragmentation. **Antigravity must map official AG report IDs to these rows or correct them.**

Legend — **Verification:** `UNVERIFIED` | `REPRODUCED` | `MITIGATED` | `CLOSED` | `BLOCKED` | `DOC_DRIFT`

| ID | Sev | Title | Evidence | Owner | Dependencies | Acceptance test / proof | Verification |
|----|-----|-------|----------|-------|--------------|---------------------------|--------------|
| META-001 | P0 | Audit SHA `3c955c7` not in repository | `PHASE0_BASELINE_RECONCILIATION.md` | Antigravity + Founder | Full SHA or artifact upload | Object exists on `origin`; tree hash recorded | **REPRODUCED** |
| AG-EPR-001 | P0 | Hosted MCP canonical authority not enforced in `apply_governance` | `governance_integration.py`; `RELEASE_SECURITY_GATE.md` | Cursor | Heart resolver, policy epoch wiring | New negative tests: hosted call refuses without canonical verdict; no synthetic ALLOW | **REPRODUCED** |
| AG-EPR-002 | P0 | Upstream dispatch skips canonical authority resolver | `upstream_dispatch.py`; gate doc | Cursor | AG-EPR-001 | Upstream tool call fails closed when resolver denies | **REPRODUCED** |
| AG-EPR-003 | P0 | Stale approval resume after epoch / policy change | Gate doc; tests on B-main | Cursor | Epoch snapshots on approval records | `test_epoch_change_after_separate_approval_dispatches_zero_times` + Antigravity fresh repro | **DOC_DRIFT** (tests pass on B-main; gate still OPEN) |
| AG-EPR-004 | P0 | Self-hosted stdio transport unrestricted (not enterprise-governed) | `mcp/server.py` header comment | Cursor | Product mode split, docs | Enterprise profile refuses ungoverned stdio OR explicit signed waiver in deployment manifest | **REPRODUCED** |
| AG-EPR-005 | P1→P0* | DNS rebinding on outbound calls | Was OPEN in gate; `net/egress.py` on B-main | Cursor | — | `test_dns_egress_security.py` rebinding cases | **MITIGATED on B-main** (*severity per Antigravity report) |
| AG-EPR-006 | P0 | Sovereignty kernel / Heart not wired to live requests | `HEART_ENTERPRISE_READINESS.md` | Cursor | Persistence, identity adapters | Production path calls `sovereignty_kernel.evaluate` before dispatch | **REPRODUCED** |
| AG-EPR-007 | P0 | No single integrated enterprise RC SHA | Open PR map | Cursor + Founder | Qualification order | One branch: green CI + signed evidence folder at one SHA | **REPRODUCED** |
| AG-EPR-008 | P1 | `resume_approval` bypass row (non-fresh authority) | Gate inventory BYPASS | Cursor | AG-EPR-001 | Resume requires fresh resolver output matching stored approval binding | **REPRODUCED** |
| AG-EPR-009 | P1 | Multi-browser acceptance matrix incomplete | `WHITEPACT_FINAL_ENTERPRISE_MASTER_REPORT.md` | Cursor | CI browsers | Playwright matrix green FF/WebKit/Chromium on RC SHA | **UNVERIFIED** |
| AG-EPR-010 | P1 | Staging performance not re-benchmarked | Enterprise master report | Cursor | Staging env | Load test artifact under `release-evidence/` for RC SHA | **BLOCKED** (no staging) |
| AG-EPR-011 | P2 | Published PyPI vs repo drift risk | `pyproject.toml` 1.3.1 on main vs older branches | Cursor | Release process | Version lockfile + provenance match RC SHA | **UNVERIFIED** |
| AG-EPR-012 | P1 | Paddle / billing live closure not on main alone | PR #107/#110 | Cursor | Sandbox credentials | E2E billing green on integrated RC | **UNVERIFIED** |
| AG-EPR-013 | P2 | Helm chart icon / marketing metadata gap | WP-V131-FIND-004 | Codex (site) / Cursor (chart) | Public logo URL | Helm lint + icon resolves | **OPEN P3** |
| AG-EPR-014 | P0 | IoT / Device Bridge implementation absent | `IOT_DEVICE_BRIDGE_HARDENING_AUDIT.md` | Cursor | Scope decision | Threat model + code OR formal descope | **REPRODUCED** |
| AG-EPR-015 | P0 | Cloud admin grants: permission + employee binding | Cloud audit §2 | Cursor | PR #128 merge | `tests/whitepact_cloud` grant postgres tests | **MITIGATED on PR #128** |
| AG-EPR-016 | P0 | Grant consume race (double spend) | `grant_repository.py` | Cursor | PR #128 | `test_postgres_atomic_consume_single_winner` | **MITIGATED on PR #128** |
| AG-EPR-017 | P1 | Enrollment vs issuance confusion | Cloud audit §3 | Cursor | PR #128 | `test_issue_rejects_unknown_employee` | **MITIGATED on PR #128** |
| AG-EPR-018 | P0 | Offboarding not fail-closed live | Cloud audit §4 | Cursor | IdP ports | Live N-* tests post-apply | **MITIGATED local; BLOCKED live** |
| AG-EPR-019 | P1 | Privileged executor disabled / unwired | `privileged_executor.py` | Cursor | Owner enablement | Staging proof with executor flag + grant | **IMPLEMENTED_NOT_DEPLOYED** |
| AG-EPR-020 | P0 | No production-shaped cloud staging | `OWNER_APPROVAL_GATE.md` | Founder + Cursor | Budget approval | Terraform apply + connectivity matrix | **BLOCKED** |
| AG-EPR-021 | P0 | Cloud identity live (CF Access JWKS) | Staging handoff | Cursor | DNS + CF | Live JWT validation tests | **BLOCKED** |
| AG-EPR-022 | P1 | CSA STAR / assurance portfolio not integrated | PR #112 | Cursor | — | Compliance gate docs + CI | **UNVERIFIED** |
| AG-EPR-023 | P2 | Codex website vs product boundary confusion | Phase 0 ownership table | Founder | — | RACI in README | **REPRODUCED (process)** |
| AG-EPR-024 | P0 | Antigravity independent validation not started | `ANTIGRAVITY_INDEPENDENT_REVIEW_HANDOFF.md` | Antigravity | META-001 + RC SHA | Signed pass/fail memo | **REPRODUCED** |

## Cloud overlap summary

- **Closed in engineering sense (PR #128, not on `main`):** AG-EPR-015, AG-EPR-016, AG-EPR-017 (local/CI).
- **Still open for enterprise product:** AG-EPR-001–004, AG-EPR-006–007, AG-EPR-014, AG-EPR-018–021, AG-EPR-024.
- **Do not double-count** cloud grant fixes as `main` production closure until merge + integrated RC CI.

## Implementation owner default

All **Cursor** rows unless marked **Codex** or **Antigravity**. Codex retains **public website** only (AG-EPR-013 web facets, corporate content).
