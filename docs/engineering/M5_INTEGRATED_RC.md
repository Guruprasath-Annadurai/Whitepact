# M5 integrated release candidate (engineering)

**Status:** `IN_PROGRESS` — **not** engineering-frozen until exact-head full CI is green.

## Candidate branch

`cursor/whitepact-ws5-m4-cloud-hardening-f7a9` (stack tip containing M1→M4 commits via #130→#134 chain).

## Required before `M5_ENGINEERING_FROZEN`

| Gate | Evidence |
|------|----------|
| Exact-head commit SHA | `git rev-parse HEAD` on candidate after push |
| Tree SHA | `git rev-parse HEAD^{tree}` |
| Full CI matrix green | GitHub Actions `CI` workflow on PR #134 (or successor) |
| M3 targeted suites | 33/33 local (see `m3_exact_head_tests.log`) |
| M5 authority campaign | `tests/test_m5_authority_regression_campaign.py` |
| PostgreSQL proofs | `tests/test_auth_real_postgres.py` (CI service) |
| Browser journey | `tests/js/customer-journey.e2e.mjs` (CI frontend job) |

## Explicit non-claims

- Cloud architecture is **not** Antigravity-qualified (`terraform validate` ≠ provision approval).
- M2/M3 independent audit may run in parallel; Cursor does not mark Antigravity PASS.
