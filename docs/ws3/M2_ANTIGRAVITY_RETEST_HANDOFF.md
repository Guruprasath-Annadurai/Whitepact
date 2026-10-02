# M2 remediation — Antigravity retest handoff (BLK-P0-06-BYPASS-01)

**Cursor status:** `M2_REMEDIATION_CI_PENDING` until exact-head full CI green on candidate below.  
**Do not interpret as Antigravity PASS.**

## Candidate (verify on GitHub)

| Field | Value |
|-------|--------|
| Branch | `cursor/whitepact-ws3-saas-unified-f7a9` |
| PR | #132 |
| Commit | `6666530ca8be23e703e689df163bcbfa412231e4` |
| Tree | `1e885bd509bf6da2caeabbec2be34500e532b76d` |
| Prior failed qualification | `6b8a3c84af76a7d3ded7db0f4ce60cb0c8e9db64` (M2 **FAIL**, P0-06 reopened) |

## Finding remediated

**BLK-P0-06-BYPASS-01:** Path-normalized aliases (`/static//index.html`, etc.) served legacy ResponsibleAI shell while canonical paths returned 404.

## Engineering evidence (Cursor)

| Control | Implementation |
|---------|----------------|
| Layer A | `canonicalize_http_path()` + canonical matching in `UnifiedSaaSLegacyRetirementMiddleware` |
| Layer B | `UnifiedSaasStaticFiles`; legacy HTML under `static/_retired_legacy_governance/` |
| Regression | `tests/test_ws3_unified_saas_legacy_frontend.py` (**48** cases, inventory + alias matrix) |
| Local log | `/opt/cursor/artifacts/blk_p0_06_bypass01_tests.log` (**48 passed**, 2026-10-02) |
| Full pytest (candidate tree) | `tests/test_ws3_unified_saas_legacy_frontend.py` — **48 passed** on WS-4 @ `ee7af39` / integrated @ `519f2d0` |

## CI gate (exact head)

| Item | Record when green |
|------|-------------------|
| Workflow run ID | `37001975576` (in progress @ push of `6666530`) |
| Python 3.11 / 3.12 | Lint · Type-check · Test jobs on PR #132 |
| Full matrix | All 18 checks on `6666530` |

When fully green, set Cursor status to **`M2 REMEDIATED — READY FOR ANTIGRAVITY RETEST`** in `docs/ws3/M2_ENGINEERING_STATUS.md` only — not PASS.

## Antigravity retest scope

1. Re-run M2 qualification matrix on **`6666530`** (or successor exact-head green SHA).
2. Explicitly exercise path-normalization bypass class (20 retired assets × alias forms).
3. Confirm no served response contains active legacy `rai_api_key` client surface in unified enterprise mode.

## Preserved register truth

- `BLK-P0-04` / `P1-01`: **VERIFIED_CLOSED** (unchanged)
- `BLK-P0-06`: **REOPENED** until Antigravity retest PASS on remediation candidate
