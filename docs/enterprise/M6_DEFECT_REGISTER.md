# M6 defect register (engineering)

| ID | Milestone | Severity | Owner | SHA / evidence | Status | Remediation | Independent qual |
|----|-----------|----------|-------|----------------|--------|-------------|------------------|
| M3-P1-TOTP-REPLAY-01 | M3 | P1 | Enterprise identity | `620399b`, `test_totp_matched_counter_security.py` | `VERIFIED_CLOSED` | Matched-counter atomic UPDATE | Antigravity M3 |
| P1-02 | M3 | P1 | Web | `620399b` | `VERIFIED_CLOSED` | Invitation adversarial tests | Antigravity M3 |
| P1-03 | M3 | P1 | SDK | `620399b` | `VERIFIED_CLOSED` | SDK contract matrix | Antigravity M3 |
| P1-04 | M3 | P1 | Billing | `620399b` | `VERIFIED_CLOSED` | Paddle sandbox | Antigravity M3 |
| BLK-P0-05 | M3 | P0 | Packaging | `620399b` | `VERIFIED_CLOSED` | Package identity | Antigravity M3 |
| P1-05 | M3 | P1 | Revocation | `620399b` | `VERIFIED_CLOSED` | Revocation kernel | Antigravity M3 |
| P1-06 | M3 | P1 | SIEM | `620399b` | `VERIFIED_CLOSED` | Export + delivery | Antigravity M3 |
| P1-07 | M3 | P1 | Lifecycle | `620399b` | `VERIFIED_CLOSED` | Data lifecycle | Antigravity M3 |
| BLK-P0-06 | M2 | P0 | Web static | `893d34a` | `VERIFIED_CLOSED` | BYPASS-01/02 | Antigravity M2 |
| M4-QUAL | M4 | — | WS-5 | `52d9b3c5497af24bb7d4a7147e33deaadc64296e` | `VERIFIED_CLOSED` | Antigravity exact-SHA PASS | **QUALIFIED** |
| M5-QUAL | M5 | — | Integration | `46685fad1ad49cfde36341ea1fad146ce1d2e714` | `VERIFIED_CLOSED` | Antigravity exact-SHA PASS | **QUALIFIED** |
| RUNBOOK-DRAFT | M6 | P3 | Ops | M6 RC | `OPEN` | Operator runbook polish | — |
| WP-LAUNCH-P1-MEMORY-SCOPE-01 | Launch | P1 | Governance | successor of `0cdef394` | `ENGINEERING_FIXED — INDEPENDENT RETEST REQUIRED` | `validate_attenuation()` now rejects a wider or missing child `memory_scope` | Antigravity |
| WP-LAUNCH-P2-ACTION-PIN-01 | Launch | P2 | Supply chain | successor of `0cdef394` | `ENGINEERING_FIXED — INDEPENDENT RETEST REQUIRED` | Pin checker sees `- uses:`; staging checkout pinned | Antigravity |
| ORIGIN-LIVE-BYPASS | Cloud | P2 | Cloud | `CLOUD_ORIGIN_PROTECTION.md` | `ENGINEERING_FIXED — INDEPENDENT RETEST REQUIRED` | Live staging drill post Gate 1 | Antigravity cloud |
| M6-QUAL | M6 | — | Engineering | `ee6e4a26becf7e89a933202651fba3b4e7a8176d` | `VERIFIED_CLOSED` | Antigravity exact-SHA PASS | **QUALIFIED** |
| SBOM-M6 | M6 | P3 | Supply chain | CI | `DEFERRED — NON-BLOCKING` | Record when generator wired | — |

Statuses allowed: `OPEN`, `ENGINEERING_FIXED — INDEPENDENT RETEST REQUIRED`, `VERIFIED_CLOSED`, `ACCEPTED_LIMITATION`, `DEFERRED — NON-BLOCKING`.
