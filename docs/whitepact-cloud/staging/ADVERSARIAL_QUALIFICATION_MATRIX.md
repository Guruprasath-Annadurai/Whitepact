# Adversarial Qualification Matrix (Phase 7)

SHA: `caf539b` — extends `docs/whitepact-cloud/11_SECURITY_TEST_RESULTS.md`

Columns: **Expected** | **Status** | **Evidence**

Status values: **VERIFIED_AUTOMATED_TESTS** | **VERIFIED_SIMULATION** | **AWAITING_LIVE_STAGING** | **NOT_TESTED**

## Identity compromise

| # | Scenario | Expected | Status | Evidence |
|---|----------|----------|--------|----------|
| 1 | Invalid authentication | Deny | **VERIFIED_AUTOMATED_TESTS** | Access JWT tests |
| 2 | Session theft / replay | Deny after consume | **VERIFIED_AUTOMATED_TESTS** | grant replay tests |
| 3 | Unauthorized privilege elevation | Deny | **VERIFIED_AUTOMATED_TESTS** | `role_allows`, issue guards |
| 4 | Employee termination | Deny grants + local revoke | **VERIFIED_AUTOMATED_TESTS** | offboarding tests |
| 5 | Forged identity header | Deny | **VERIFIED_AUTOMATED_TESTS** | `test_rejects_forwarded_identity_header` |
| 6 | Unauthorized device | Deny at Access | **NOT_TESTED** | device posture |

## Infrastructure compromise

| # | Scenario | Expected | Status | Evidence |
|---|----------|----------|--------|----------|
| 7 | Direct origin bypass | Block | **AWAITING_LIVE_STAGING** | N-02 |
| 8 | Lateral movement SaaS→exec | Deny | **AWAITING_LIVE_STAGING** | N-08 |
| 9 | Firewall failure after reboot | Rules persist | **AWAITING_LIVE_STAGING** | N-10 |
| 10 | Prohibited outbound (exec) | Deny | **AWAITING_LIVE_STAGING** | N-06 |
| 11 | Access infra secrets from SaaS | Deny | **AWAITING_LIVE_STAGING** | A-07 |

## Authorization compromise

| # | Scenario | Expected | Status | Evidence |
|---|----------|----------|--------|----------|
| 12 | Grant replay | Deny | **VERIFIED_AUTOMATED_TESTS** | consumed_at |
| 13 | Concurrent double consume | One winner | **VERIFIED_AUTOMATED_TESTS** | atomic test |
| 14 | Stale approval | Deny if policy/approval invalid | **VERIFIED_AUTOMATED_TESTS** | approval_required path |
| 15 | Expired grant | Deny | **VERIFIED_AUTOMATED_TESTS** | expired test |
| 16 | Execution without verified grant | Deny | **VERIFIED_AUTOMATED_TESTS** | executor tests |
| 17 | Permission not in employee JSON | Deny | **VERIFIED_AUTOMATED_TESTS** | allowlist test |

## Operational compromise

| # | Scenario | Expected | Status | Evidence |
|---|----------|----------|--------|----------|
| 18 | Backup deletion | Backup role cannot delete | **AWAITING_LIVE_STAGING** | B-07 |
| 19 | Audit log tampering | Append-only evidence tables | **IMPLEMENTED** | classification erasable=false |
| 20 | IdP outage | Fail closed (no bypass header) | **AWAITING_LIVE_STAGING** |
| 21 | Access gateway outage | No admin access | **AWAITING_LIVE_STAGING** |
| 22 | Emergency recovery | Break-glass path works | **AWAITING_LIVE_STAGING** | B-05 |
| 23 | DB restoration | Consistent grants | **AWAITING_LIVE_STAGING** | B-04 |

## Qualification bar

**Corporate SaaS staging gate:** all **AWAITING_LIVE_STAGING** rows for tiers 7–11 and 18–23 executed with owner evidence.

**Current:** Engineering CI green on `caf539b`; **live adversarial gate open = no**.
