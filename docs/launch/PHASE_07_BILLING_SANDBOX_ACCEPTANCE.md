# Phase 7 — Billing sandbox acceptance

**Gate: NOT EXECUTED in this session.**

Prior engineering recorded Paddle sandbox coverage on earlier milestones (`P1-04` in `docs/enterprise/M6_DEFECT_REGISTER.md`, status `VERIFIED_CLOSED` at SHA `620399b` by the M3 note). That disposition is not a new test run on `0cdef394` or on this successor.

## Acceptance the owner can ask a reviewer to repeat

Against the sandbox adapter only:

1. Create a subscription event once. The tenant plan changes once.
2. Deliver the same webhook id again. The plan does not change a second time and no second invoice side effect is recorded.
3. Deliver a failed-payment event. The tenant is marked past due according to the owner policy. Grants already issued expire on their own TTL. New consequential grants follow the suspension rule the owner chose.
4. Deliver an unsigned or wrongly signed webhook. It is rejected and the plan does not change.
5. Cancel. Export of the tenant's evidence still works until the retention date the owner set. Execution grants stop.

No live Paddle key was used here. Do not point these tests at production webhook URLs.

## Gate

NOT EXECUTED for this successor.
