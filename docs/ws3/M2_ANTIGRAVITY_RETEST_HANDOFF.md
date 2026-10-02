# M2 remediation — Antigravity retest handoff (BLK-P0-06-BYPASS-01/02)

**Antigravity disposition:** **M2 FULL PASS — EXACT-SHA QUALIFIED** @ `893d34a` (CI `37022536095`).  
**Do not modify or reinterpret this qualification.**

## Frozen exact CI head (M2)

| Field | Value |
|-------|--------|
| Branch | `cursor/whitepact-ws3-saas-unified-f7a9` |
| PR | #132 |
| **Frozen exact CI head** | `893d34a9d009560a3d9f07887c1afa3018f9e6dc` |
| Tree (frozen head) | `ef47788f8c6b10f5a34c178588335ce3c8e7c611` |
| BYPASS-02 implementation anchor | `d13caa114576d95eb20170eb1858387956103ae5` |
| Prior failed qualification | `6b8a3c84af76a7d3ded7db0f4ce60cb0c8e9db64` (M2 **FAIL**, P0-06 reopened) |

## Findings remediated

**BLK-P0-06-BYPASS-01:** Path-normalized aliases served legacy ResponsibleAI shell.  
**BLK-P0-06-BYPASS-02:** Retired HTML under `/static/_retired_legacy_governance/*` returned 200.

## Engineering evidence (Cursor)

| Control | Implementation |
|---------|----------------|
| Layer A | `canonicalize_http_path()` + canonical matching in `UnifiedSaaSLegacyRetirementMiddleware` |
| Layer B | Legacy shell under `legacy_templates/` (not mounted); unified static **allowlist** + namespace deny |
| BYPASS-02 | `GET /static/_retired_legacy_governance/*` → **404**; alias matrix in tests |
| Regression | `tests/test_ws3_unified_saas_legacy_frontend.py` (**48** cases) |

## CI gate (exact head)

| Item | Value |
|------|--------|
| Workflow run ID | `37022536095` — **success** |
| Python 3.11 / 3.12 | Lint · Type-check · Test — **success** |
| Full matrix | **18/18** checks **SUCCESS** on frozen head `893d34a` |

## Preserved register truth

- `BLK-P0-04` / `P1-01`: **VERIFIED_CLOSED**
- `BLK-P0-06` / BYPASS-01 / BYPASS-02: **VERIFIED_CLOSED** (Antigravity M2)
