# WS-4 / M3 — engineering status

**Branch:** `cursor/whitepact-ws4-m3-enterprise-f7a9` (stacked on qualified WS-3 / M2)  
**Cursor status:** `M3 = FULL PASS — EXACT-SHA QUALIFIED` (Antigravity)  
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

`tests/test_m3_adversarial_security_campaign.py` — focused M3 matrix (run before exact-head CI gate).

## Exact-head gate (PR #136)

| Field | Value |
|-------|--------|
| Branch | `cursor/whitepact-m3-qualification-gate-f7a9` |
| HEAD | `620399b7973f5ed058d45218610be228e72d3ed8` |
| Tree | `15b7934d93ad8692f5a5e8c2225c5f69c130da00` |
| CI | **18/18** — `37107348827` |
| Security fix | `M3-P1-TOTP-REPLAY-01` @ `fb196fd` |
| Superseded | `656de8a` (CI-only; not independently qualified) |

Artifact: `/opt/cursor/artifacts/m3_qualification_gate_620399b_ci.json`  

**Antigravity qualification:** `620399b` / tree `15b7934d…` — `M3-P1-TOTP-REPLAY-01`, P1-02…P1-07, BLK-P0-05 **VERIFIED_CLOSED**.  
Forward lineage base: use exact M3 SHA above (do not reinterpret).
