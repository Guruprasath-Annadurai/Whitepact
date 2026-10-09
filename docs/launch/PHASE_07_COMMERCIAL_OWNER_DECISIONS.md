# Phase 7 — Commercial owner decisions

**None of the following are decided by engineering.**

| # | Decision | Engineering behavior until decided |
|---|----------|-------------------------------------|
| 1 | Which plans are in the first commercial launch | Do not add prices to the website or API responses as if they were approved |
| 2 | Trial length, if any | Do not start trials |
| 3 | What suspension does to in-flight grants | Fail closed: do not issue new grants; do not delete evidence |
| 4 | Refunds | No refund workflow beyond recording the provider event |
| 5 | Tax treatment and merchant of record | No tax calculation invented in the app |
| 6 | Payment provider for launch | Keep the existing Paddle sandbox path isolated; do not add another provider |
| 7 | Data retention after cancel | Do not shorten or lengthen retention in code |
| 8 | Support channel and hours | Do not publish an SLA |

Paid subscriptions stay off until items 1, 5, and 6 are written down by the owner.

## Gate

BLOCKED.
