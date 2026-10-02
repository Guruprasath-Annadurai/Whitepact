# WS-4 / M3 — engineering status

**Branch:** `cursor/whitepact-ws4-m3-enterprise-f7a9` (stacked on WS-3 / M2 head)  
**Cursor status:** `IN_PROGRESS`

## Prerequisites

- M2 marked **M2_ENGINEERING_COMPLETE — READY_FOR_INDEPENDENT_AUDIT** on `cursor/whitepact-ws3-saas-unified-f7a9` (`8591043`).

## M3 targets (open)

| ID | Scope | Notes |
|----|--------|--------|
| P1-02 | Team invitations | Existing web + IAM tests; extend adversarial matrix + session invalidation on role change |
| P1-03 | SDK governance | Python/TS contract tests vs runtime |
| P1-04 | Paddle sandbox | No production activation |
| BLK-P0-05 | Package/product identity | `docs/PACKAGE_IDENTITY.md`; wheel/CLI coherence without public publish |
| P1-05 | Break-glass | Operational UNKNOWN/reconciliation paths |
| P1-06 | SIEM export | Structured streaming + failure modes |
| P1-07 | Data lifecycle | Deletion vs evidence retention |

## Next engineering actions

1. Dedicated `tests/test_web_invitations_adversarial.py` aligned to M3 §20 scenarios.
2. Paddle webhook replay/out-of-order harness (sandbox only).
3. SDK differential contract suite.
