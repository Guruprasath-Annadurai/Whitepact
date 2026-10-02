# M5 integrated release candidate (engineering)

**Status:** `IN_PROGRESS` — **not** engineering-frozen until exact-head full CI is green.

## Candidate (PR #135 → `main`)

| Field | Value |
|-------|--------|
| Branch | `cursor/whitepact-m5-integrated-rc-f7a9` |
| Commit | Verify `git rev-parse HEAD` after push |
| Tree | `git rev-parse HEAD^{tree}` |
| PR | https://github.com/Guruprasath-Annadurai/Whitepact/pull/135 |
| M2 ancestor | `893d34a9d009560a3d9f07887c1afa3018f9e6dc` (must be ancestor) |
| M3 ancestor | `c281954a3c49094df7a7b19044c3035ef40f54c8` (must be ancestor) |

## Required before `M5_ENGINEERING_FROZEN`

| Gate | Evidence |
|------|----------|
| Full CI matrix green | GitHub Actions on PR **#135** (18/18) |
| M3 adversarial campaign | `tests/test_m3_adversarial_security_campaign.py` |
| M5 authority campaign | `tests/test_m5_authority_regression_campaign.py` |
| PostgreSQL proofs | `tests/test_auth_real_postgres.py` (CI service) |
| Browser journey | `tests/js/customer-journey.e2e.mjs` (CI frontend job) |

## Explicit non-claims

- Cloud architecture is **not** Antigravity-qualified (`terraform validate` ≠ provision approval).
- M2 **FULL PASS** is Antigravity-qualified @ `893d34a`; M3/M5 independent audit not claimed by Cursor.
