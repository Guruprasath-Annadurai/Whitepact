# M2 remediation — Antigravity retest handoff (BLK-P0-06-BYPASS-01)

**Cursor status:** **`M2 REMEDIATED AGAIN — READY FOR ANTIGRAVITY RETEST`** (BLK-P0-06-BYPASS-02).  
**Do not interpret as Antigravity PASS.**

## Candidate (verify on GitHub)

| Field | Value |
|-------|--------|
| Branch | `cursor/whitepact-ws3-saas-unified-f7a9` |
| PR | #132 |
<<<<<<< HEAD
| Commit | *(new exact-head SHA after BYPASS-02 fix — verify on PR #132)* |
=======
| Commit | `d13caa114576d95eb20170eb1858387956103ae5` |
| Tree | `ead40b9cb77f4e8b76b2bc3b92e82d666fbc9f17` |
| Parent | `541a9036004ba0225665bc72ef2426f72efa3385` |
>>>>>>> b863434 (fix(ci): i18n test path + StrEnum after legacy_templates move)
| Prior failed retest | `6666530ca8be23e703e689df163bcbfa412231e4` (BYPASS-01 mitigated; BYPASS-02 open) |
| Prior failed qualification | `6b8a3c84af76a7d3ded7db0f4ce60cb0c8e9db64` (M2 **FAIL**, P0-06 reopened) |

## Finding remediated

**BLK-P0-06-BYPASS-01:** Path-normalized aliases (`/static//index.html`, etc.) served legacy ResponsibleAI shell while canonical paths returned 404.

## Engineering evidence (Cursor)

| Control | Implementation |
|---------|----------------|
| Layer A | `canonicalize_http_path()` + canonical matching in `UnifiedSaaSLegacyRetirementMiddleware` |
| Layer B | Legacy shell under `legacy_templates/` (not mounted); unified static **allowlist** + namespace deny |
| BYPASS-02 | `GET /static/_retired_legacy_governance/*` → **404**; 18×7 namespace alias matrix in tests |
| Regression | `tests/test_ws3_unified_saas_legacy_frontend.py` (**48** cases, inventory + alias matrix) |
| Local log | `/opt/cursor/artifacts/blk_p0_06_bypass01_tests.log` (**48 passed**, 2026-10-02) |
| Full pytest (candidate tree) | `tests/test_ws3_unified_saas_legacy_frontend.py` — **48 passed** on WS-4 @ `ee7af39` / integrated @ `519f2d0` |

## CI gate (exact head)

| Item | Record when green |
|------|-------------------|
| Workflow run ID | `37001975576` — **success** |
| Python 3.11 / 3.12 | Lint · Type-check · Test — **success** |
| Full matrix | **18/18** checks **SUCCESS** on `6666530` |
| Path-normalization regression | `tests/test_ws3_unified_saas_legacy_frontend.py` — **48 passed** (`/opt/cursor/artifacts/m2_candidate_6666530_full_legacy_suite.log`) |

**Antigravity:** retest this **exact commit** only; Cursor does **not** claim M2 PASS.

## Antigravity retest scope

1. Re-run M2 qualification matrix on **`6666530`** (or successor exact-head green SHA).
2. Explicitly exercise path-normalization bypass class (20 retired assets × alias forms).
3. Confirm no served response contains active legacy `rai_api_key` client surface in unified enterprise mode.

## Preserved register truth

- `BLK-P0-04` / `P1-01`: **VERIFIED_CLOSED** (unchanged)
- `BLK-P0-06`: **REOPENED** until Antigravity retest PASS on remediation candidate
