# Phase 0 — P0 reproduction log

Reproductions run in the Cloud Agent VM on **2026-09-30**. No finding is marked **RESOLVED** here—only **REPRODUCED**, **NOT REPRODUCED (baseline missing)**, or **CONTRADICTED BY TEST (doc drift—Antigravity must confirm)**.

## Baselines used

| Baseline | SHA | Role |
|----------|-----|------|
| B-main | `81beb3ac50e17068c7d6f26d9a07f2cb0442dbec` | Merged product line |
| B-cloud | `7386fadf8c88dc78044e9e7aceef9b655f6496b2` | PR #128 (not reproduced in this log—see cloud audit report) |
| B-audit | `3c955c7` | **Unavailable** |

## P0-class reproduction matrix

| Register ID | Title | Baseline | Command / evidence | Result |
|-------------|-------|----------|-------------------|--------|
| AG-EPR-001 | Hosted canonical authority bypass (`apply_governance` synthetic `AuthorityContext`) | B-main | Code inspection: `src/responsibleai/mcp/governance_integration.py` constructs `AuthorityContext` without sovereignty kernel / canonical resolver. `pytest tests/test_phase1_authority.py -q --no-cov` → **37 passed** (compatibility, not closure proof). | **REPRODUCED (architectural)** — OPEN until wired |
| AG-EPR-002 | Upstream canonical authorization gap (`upstream_dispatch`) | B-main | Same file family; `pytest tests/test_upstream_gateway.py` not re-run full suite in Phase 0 slice. Gate doc row: OPEN P0. | **REPRODUCED (documented)** — needs targeted Antigravity replay |
| AG-EPR-003 | Stale approval resume after governance epoch change | B-main | `pytest tests/test_resume_after_approval.py -q --no-cov -k epoch_change` → `test_epoch_change_after_separate_approval_dispatches_zero_times` **1 passed**. Also `tests/test_policy_privileged_governance.py::test_security_epoch_changed_after_approval_blocked` **passed**. | **CONTRADICTED BY TEST vs RELEASE_SECURITY_GATE** — treat as **RE-VERIFY P0** |
| AG-EPR-004 | Community stdio unrestricted tool access (enterprise production posture) | B-main | `src/responsibleai/mcp/server.py` documents stdio as “full unrestricted tool access”; no governance gate on stdio path by design. | **REPRODUCED (by design)** — enterprise blocker unless scoped |
| AG-EPR-005 | DNS rebinding on outbound HTTP | B-main | `pytest tests/test_dns_egress_security.py -q --no-cov -k rebinding` → **3 passed**; `src/responsibleai/net/egress.py` present on B-main. | **NOT REPRODUCED on B-main** (mitigation present); Antigravity confirm vs audit SHA |
| AG-EPR-006 | Sovereignty kernel not on live execution path | B-main | `docs/heart/HEART_ENTERPRISE_READINESS.md` § “No live wiring”. | **REPRODUCED (documented)** |
| AG-EPR-007 | Fragmented RC (no single integrated SHA) | Repo | Open PRs #107, #108, #128, #124, etc.; table in baseline doc. | **REPRODUCED** |
| AG-EPR-008 | Audit baseline SHA `3c955c7` missing | Repo | `git cat-file`, `ls-remote` | **REPRODUCED (process)** |

### WhitePact Cloud P0-adjacent (reproduced via prior campaign—not re-run on `7386fad` in this VM slice)

| Register ID | Evidence source | Result |
|-------------|-----------------|--------|
| AG-EPR-015–019 | `docs/whitepact-cloud/WHITEPACT_CLOUD_FINAL_AUDIT_REPORT.md`, CI run `36624924439` on `7743dd5` | Controls **VERIFIED** in CI; live staging **NOT REPRODUCED** |
| AG-EPR-020–021 | `docs/whitepact-cloud/staging/OWNER_APPROVAL_GATE.md` | **BLOCKED** by policy (no apply) |

## Hosted MCP governance slice (regression guard)

On B-main (detached `origin/main` checkout):

```text
pytest tests/test_resume_after_approval.py tests/test_phase1_release_gate.py \
  tests/test_phase1_authority.py tests/test_mcp_server_gating.py -q --no-cov --tb=line
→ 60 passed, 11 warnings, ~7s
```

## Remedy compatibility notes (fail-closed)

| Proposed remedy class | Risk if applied bluntly |
|-----------------------|-------------------------|
| Enable unrestricted stdio “governance” | Breaks Community open-core contract; must remain **explicit enterprise mode** with separate transport policy |
| Merge all open PRs to “fix integration” | Violates qualification rules; needs ordered integration branch + CI |
| Force-enable `PRIVILEGED_EXECUTOR` in staging | Expands blast radius before live IdP/JWKS proof |
| Delete legacy governance paths | Mass rewrite risk—dependency analysis required |

## Antigravity action

Re-run this matrix on the **true** audit SHA once supplied, and sign off each row in [PHASE0_MASTER_DEFECT_REGISTER.md](./PHASE0_MASTER_DEFECT_REGISTER.md).
