# WS-4 / M3 — engineering status

<<<<<<< HEAD
**Branch:** `cursor/whitepact-ws4-m3-enterprise-f7a9` (stacked on qualified WS-3 / M2)  
**Cursor status:** `M3_ENGINEERING_IN_PROGRESS — TARGETED_CAMPAIGN`  
**Prerequisite:** M2 **FULL PASS — EXACT-SHA QUALIFIED** @ `893d34a` (Antigravity; CI `37022536095`)
=======
**Branch:** `cursor/whitepact-ws4-m3-enterprise-f7a9` (stacked on WS-3 / M2)  
**Cursor status:** `M3_ENGINEERING_IN_PROGRESS — EXACT_HEAD_CI_PENDING`  
<<<<<<< HEAD
**Local targeted gate:** 33/33 pytest slices passed (see `/opt/cursor/artifacts/m3_exact_head_tests.log`).  
**Exact-head freeze:** record `git rev-parse HEAD` on PR **#133** only after full CI matrix green (Antigravity certifies independently).
=======
**Engineering freeze:** record exact `git rev-parse HEAD` on PR **#133** only after stacked exact-head full CI green (Antigravity certifies independently).
>>>>>>> origin/cursor/whitepact-ws4-m3-enterprise-f7a9

## Prerequisites

- M2 **M2_ENGINEERING_COMPLETE — READY_FOR_INDEPENDENT_AUDIT** on `cursor/whitepact-ws3-saas-unified-f7a9`.
>>>>>>> origin/cursor/whitepact-ws5-m4-cloud-hardening-f7a9

## M3 targets

| ID | Scope | Engineering evidence |
|----|--------|----------------------|
| P1-02 | Team invitations | `tests/test_web_invitations_adversarial.py` |
| P1-03 | SDK governance | `tests/test_sdk_governance_contract_matrix.py`, `tests/test_sdk_governance_reconciliation_m3.py` |
| P1-04 | Paddle sandbox | `tests/test_paddle_sandbox_matrix_m3.py` → canonical Paddle suites |
| BLK-P0-05 | Package identity | `tests/test_package_identity_m3.py`, `docs/PACKAGE_IDENTITY.md` |
| P1-05 | Break-glass / revocation | `tests/test_break_glass_runtime_m3.py`, governance revoke slices |
| P1-06 | SIEM export + delivery | `tests/test_siem_audit_export.py`, `tests/test_siem_delivery_m3.py` |
| P1-07 | Data lifecycle | `tests/test_web_account_lifecycle_m3.py` |

## Adversarial campaign

`tests/test_m3_adversarial_security_campaign.py` — focused M3 matrix (run before exact-head CI gate).

## Exact-head gate

When campaign + full local matrix green, push one M3 candidate SHA and run PR **#133** full CI.  
Mark **`M3_ENGINEERING_COMPLETE — READY_FOR_ANTIGRAVITY`** only after **18/18** green — not independent PASS.
