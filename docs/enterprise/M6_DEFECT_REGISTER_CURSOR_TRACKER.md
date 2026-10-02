# M6 — canonical defect register (Cursor engineering tracker)

**Status:** DRAFT — evidence populated as integrated RC gates close.  
**Not** Antigravity independent disposition.

## P0 (launch-critical in enterprise scope)

| ID | Severity | Engineering state | Independent state | Regression anchor |
|----|----------|-------------------|-------------------|-------------------|
| BLK-P0-02 | P0 | Closed on branch (WS-2) | **VERIFIED_CLOSED** | `tests/test_mcp_ws2_authority_matrix.py` |
| BLK-P0-03 | P0 | Closed on branch (WS-2) | **VERIFIED_CLOSED** | WS-2 authority / trust domain suites |
| BLK-P0-04 | P0 | WS-3 SPA approvals | **VERIFIED_CLOSED** | `customer-journey.e2e.mjs`, web contract tests |
| BLK-P0-06 | P0 | **REMEDIATED** @ `6666530` (CI **18/18** run `37001975576`) | **REOPENED** — Antigravity retest required | `tests/test_ws3_unified_saas_legacy_frontend.py` (48) |

## P1 (programme scope)

| ID | Engineering | Independent | Notes |
|----|-------------|-------------|-------|
| P1-01 | WS-3 policy UI | **VERIFIED_CLOSED** | |
| P1-02 | Invitations adversarial | Pending Antigravity | `tests/test_web_invitations_adversarial.py` |
| P1-03 | SDK governance | Pending | contract matrix tests |
| P1-04 | Paddle sandbox | Pending | canonical Paddle suites |
| P1-05 | Break-glass revoke | Pending | governance API + M3 slice |
| P1-06 | SIEM export/delivery | Pending | export + forwarder tests |
| P1-07 | Account lifecycle | Pending | transfer + delete tests |
| BLK-P0-05 | Package identity | Pending | wheel smoke M3 |

## Cloud (no provision)

| Register | State |
|----------|--------|
| CLOUD-AG-01..07 | **BLOCKED — UNSAFE TO PROVISION** |
| Terraform | `terraform validate` only (`tests/test_terraform_m4_validate.py`) |
