# WS-4 / M3 — engineering status

**Branch:** `cursor/whitepact-ws4-m3-enterprise-f7a9` (stacked on WS-3 / M2)  
**Cursor status:** `M3_ENGINEERING_IN_PROGRESS — EXACT_HEAD_CI_PENDING`  
**Local targeted gate:** 33/33 pytest slices passed (see `/opt/cursor/artifacts/m3_exact_head_tests.log`).  
**Exact-head freeze:** record `git rev-parse HEAD` on PR **#133** only after full CI matrix green (Antigravity certifies independently).

## Prerequisites

- M2 **M2_ENGINEERING_COMPLETE — READY_FOR_INDEPENDENT_AUDIT** on `cursor/whitepact-ws3-saas-unified-f7a9`.

## M3 targets

| ID | Scope | Engineering evidence |
|----|--------|----------------------|
| P1-02 | Team invitations | `tests/test_web_invitations_adversarial.py` |
| P1-03 | SDK governance | `sdk/python/rai_client/governance.py`, `sdk/typescript/src/governance.ts`, `tests/test_sdk_governance_contract.py`, `tests/test_sdk_governance_contract_matrix.py`, `tests/fixtures/governance_sdk_contract.py` |
| P1-04 | Paddle sandbox | `tests/test_paddle_sandbox_matrix_m3.py` → canonical Paddle suites |
| BLK-P0-05 | Package identity | `docs/PACKAGE_IDENTITY.md`, `pyproject.toml`, `tests/test_package_identity_m3.py` |
| P1-05 | Break-glass / revocation | `tests/test_break_glass_runtime_m3.py` + `tests/test_governance_api.py` delegation revoke |
| P1-06 | SIEM export + delivery | `siem_export.py`, `siem_delivery.py`, `tests/test_siem_audit_export.py`, `tests/test_siem_delivery_m3.py` |
| P1-07 | Data lifecycle | `tests/test_web_account_lifecycle_m3.py` (sole-owner guard, transfer-then-delete) |

## Next

- Stack **M4** (`cursor/whitepact-ws5-m4-cloud-hardening-f7a9`): Terraform plan-only validation, PostgreSQL concurrency, SSO/SCIM/a11y/tracing — **no cloud provision**.
