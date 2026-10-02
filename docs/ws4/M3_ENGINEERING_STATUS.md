# WS-4 / M3 — engineering status

**Branch:** `cursor/whitepact-ws4-m3-enterprise-f7a9` (stacked on qualified WS-3 / M2)  
**Frozen engineering head:** `6979a518ee7194dc539f5417384df2f776efd937`  
**Cursor status:** `M3_ENGINEERING_IN_PROGRESS — EXACT_HEAD_CI_PENDING`  
**Prerequisite:** M2 **FULL PASS — EXACT-SHA QUALIFIED** @ `893d34a` (Antigravity; CI `37022536095`)

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

`tests/test_m3_adversarial_security_campaign.py` — **14/14** local (`/opt/cursor/artifacts/m3_adversarial_campaign.log`).

## Exact-head gate

Full CI: `cursor/whitepact-m3-qualification-gate-f7a9` → `main` at **exact** `6979a51` (`docs/ws4/M3_QUALIFICATION_GATE.md`).  
PR **#135** is diagnostic only (rewritten history; not M3 freeze).  
Mark **`M3_ENGINEERING_COMPLETE — READY_FOR_ANTIGRAVITY`** only after **18/18** on **`6979a51`** — not independent PASS.
