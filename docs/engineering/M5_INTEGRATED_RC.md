# M5 integrated release candidate (engineering)

**Status:** `IN_PROGRESS` — **not** engineering-frozen until exact-head full CI is green.

## Candidate (PR #135 → `main`)

| Field | Value (2026-10-02) |
|-------|---------------------|
| Branch | `cursor/whitepact-m5-integrated-rc-f7a9` |
| Commit | `519f2d0f51bce9f76392bda8821b76beaf28cee1` |
| Tree | `b0f4c72dc533e27d3c1e7b27d883334534680548` |
| Prior candidate | `702d277fe8efeda455c75eff5e246c7289581dad` (superseded by gate/test doc cherry-pick) |
| PR | https://github.com/Guruprasath-Annadurai/Whitepact/pull/135 |

Squashed single commit for DCO + coherent M5 gate (stacked multi-commit history remains on #130–#134).

## Required before `M5_ENGINEERING_FROZEN`

| Gate | Evidence |
|------|----------|
| Full CI matrix green | GitHub Actions on PR **#135** |
| M3 targeted suites | 33/33 local (`/opt/cursor/artifacts/m3_exact_head_tests.log`) |
| M5 authority campaign | `tests/test_m5_authority_regression_campaign.py` |
| PostgreSQL proofs | `tests/test_auth_real_postgres.py` (CI service) |
| Browser journey | `tests/js/customer-journey.e2e.mjs` (CI frontend job) |

## Explicit non-claims

- Cloud architecture is **not** Antigravity-qualified (`terraform validate` ≠ provision approval).
- M1 `BLK-P0-02` / `BLK-P0-03`: **VERIFIED_CLOSED** (Antigravity); M2 qualification in flight.
