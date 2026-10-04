# M6 defect register (engineering)

| ID | Milestone | Severity | Owner | SHA / evidence | Status | Remediation | Independent qual |
|----|-----------|----------|-------|----------------|--------|-------------|------------------|
| M3-P1-TOTP-REPLAY-01 | M3 | P1 | Enterprise identity | `620399b`, `test_totp_matched_counter_security.py` | `VERIFIED_CLOSED` | Matched-counter atomic UPDATE | Antigravity M3 |
| P1-02 | M3 | P1 | Web | `620399b`, invitation adversarial tests | `VERIFIED_CLOSED` | — | Antigravity M3 |
| P1-03 | M3 | P1 | SDK | `620399b`, SDK contract matrix | `VERIFIED_CLOSED` | — | Antigravity M3 |
| P1-04 | M3 | P1 | Billing | `620399b`, Paddle sandbox tests | `VERIFIED_CLOSED` | Sandbox only | Antigravity M3 |
| BLK-P0-05 | M3 | P0 | Packaging | `620399b` | `VERIFIED_CLOSED` | Package identity | Antigravity M3 |
| P1-05 | M3 | P1 | Revocation | `620399b`, break-glass / revocation | `VERIFIED_CLOSED` | — | Antigravity M3 |
| P1-06 | M3 | P1 | SIEM | `620399b`, export + delivery | `VERIFIED_CLOSED` | — | Antigravity M3 |
| P1-07 | M3 | P1 | Lifecycle | `620399b` | `VERIFIED_CLOSED` | — | Antigravity M3 |
| BLK-P0-06 | M2 | P0 | Web static | `893d34a` | `VERIFIED_CLOSED` | BYPASS-01/02 | Antigravity M2 |
| M4-QUAL | M4 | — | WS-5 | `52d9b3c5497af24bb7d4a7147e33deaadc64296e` | `VERIFIED_CLOSED` | Antigravity **FULL PASS (EXACT-SHA)** | **QUALIFIED** |
| M5-RC-FREEZE | M5 | — | Integration | `c77bdef` @ CI `37188931027` | `ENGINEERING_FIXED — INDEPENDENT RETEST REQUIRED` | 18/18 green; Antigravity M5 pending | **PENDING** |
| RUNBOOK-DRAFT | M6 | P3 | Ops | prep branch | `OPEN` | Complete operator runbooks | — |
| ORIGIN-LIVE-BYPASS | M4/M6 | P2 | Cloud | static tests only | `ACCEPTED LIMITATION` | Staging drill post-deploy | — |

Do not delete rows; update status with evidence links when state changes.
