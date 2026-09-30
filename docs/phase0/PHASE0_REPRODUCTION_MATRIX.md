# Phase 0 — Exact-baseline reproduction matrix

**Audit SHA:** `3c955c7` — **not reproduced** (object unknown). No claim of reproducing Antigravity’s original checkout.

## Baselines

| Code | SHA / ref | Use |
|------|-----------|-----|
| **B-main** | `81beb3ac50e17068c7d6f26d9a07f2cb0442dbec` | Current merged `origin/main` |
| **B-combined-rc** | `6190cc7a9874d0ad0778c2b5ae3179fbc978aa16` | PR #107 tip |
| **B-cloud** | `7386fadf8c88dc78044e9e7aceef9b655f6496b2` | PR #128 tip |
| **B-published** | PyPI `rai-governance-platform` 1.3.1 (per `pyproject.toml` on B-main) | Package identity checks |
| **B-integrated-rc** | *TBD* | After qualification — not declared in Phase 0 |

## Reproduction commands (B-main, VM 2026-09-30)

```bash
git checkout 81beb3ac50e17068c7d6f26d9a07f2cb0442dbec
pip install -e . -q && whitepact --help | head -5          # BLK-P0-01
pytest tests/test_mcp_server_gating.py -q --no-cov         # hosted governance slice
pytest tests/test_resume_after_approval.py -q --no-cov -k epoch_change  # epoch resume
pytest tests/test_dns_egress_security.py -q --no-cov -k rebinding       # SUP-002
```

Hosted governance slice (B-main): **60 passed** (`test_resume_after_approval`, `test_phase1_release_gate`, `test_phase1_authority`, `test_mcp_server_gating`).

## Matrix (official 24)

| ID | Baseline | Method | Result label |
|----|----------|--------|--------------|
| BLK-P0-01 | B-main | `whitepact --help`; `pyproject.toml` scripts | **REPRODUCED** |
| BLK-P0-02 | B-main | `mcp/server.py` stdio path review | **REPRODUCED** |
| BLK-P0-03 | B-main | Heart readiness doc + code search for live `sovereignty_kernel` wiring | **REPRODUCED** |
| BLK-P0-04 | B-main | `web/` approvals panel vs legacy static | **PARTIALLY_MITIGATED** |
| BLK-P0-05 | B-main | `pyproject.toml` name vs `whitepact` CLI | **REPRODUCED** |
| BLK-P0-06 | B-main | `app.py` SPA mounts + legacy HTML | **REPRODUCED** |
| BLK-P1-01 | B-main | `web/src/App.tsx` routes; dashboard tests | **REPRODUCED** |
| BLK-P1-02 | B-main | Invitations API + UI; no live email proof | **PARTIALLY_MITIGATED** |
| BLK-P1-03 | B-main | `sdk/typescript/src/client.ts` API surface | **REPRODUCED** |
| BLK-P1-04 | B-main | Paddle wiring in `dashboard/app.py`; B-combined-rc for closure delta | **REPRODUCED** on B-main |
| BLK-P1-05 | B-main | Code search break-glass / interrupt | **REPRODUCED** |
| BLK-P1-06 | B-main | Incident SIEM payload vs streaming | **REPRODUCED** |
| BLK-P1-07 | B-main | Account erasure workflow search | **REPRODUCED** |
| BLK-P1-08 | B-cloud | Terraform/LB modules; no live apply | **REPRODUCED** (design) |
| BLK-P2-01 | B-main | Runtime lease docs | **REPORT_ONLY** |
| BLK-P2-02 | B-main | SAML/OIDC without SCIM | **REPRODUCED** |
| BLK-P2-03 | B-main | CI a11y job exists; no fresh audit log attached | **REPORT_ONLY** |
| BLK-P2-04 | B-main | OTEL partial | **REPORT_ONLY** |
| BLK-P2-05 | B-main | Audit APIs | **REPORT_ONLY** |
| BLK-P2-06 | B-main / B-cloud | No restore drill executed | **REPRODUCED** |
| BLK-P3-01 | B-main | Legacy URI/branding grep | **REPRODUCED** |
| BLK-P3-02 | B-main | Doc inventory | **REPORT_ONLY** |
| BLK-P3-03 | B-main | Hatch wheel packages | **REPRODUCED** |
| BLK-P3-04 | B-main | Component review only | **REPORT_ONLY** |

## Cloud principal findings (Antigravity submitted)

Reproduction against live staging was **not** performed (provisioning blocked). Engineering state documented on **B-cloud**; verdict **BLOCKED — UNSAFE TO PROVISION**. See cloud register.
