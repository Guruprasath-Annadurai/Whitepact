# WhitePact v1.3.1 — Cursor release closure report

## 1–6 Identity

| Field | Value |
| --- | --- |
| Baseline SHA (v1.3.0 merge) | `b3e9d6072105a25c63b2915658bb74f31296c9a8` |
| Branch | `cursor/v1.3.1-final-enterprise-hardening` |
| PR | [#114](https://github.com/Guruprasath-Annadurai/Whitepact/pull/114) |
| Version | **1.3.1** |
| Pre-closure SHA | `fe3c5f0…` |
| Post-closure SHA | *(see git log after push)* |

## 7 Files changed (this closure pass)

- `tests/test_alembic_ini_resolution.py` — remove unused `import os` (F401)
- `sdk/typescript/package.json`, `sdk/python/pyproject.toml` — **1.3.1**
- `docs/PACKAGE_IDENTITY.md`, `README.md` — naming clarity
- `scripts/run_v131_production_tool_benchmarks.py`, `scripts/v131_sdk_cli_acceptance.py`
- `WHITEPACT_V131_*` evidence documents
- Ruff format on branch-touched Python files (no lint config changes)

## 8 CI blocker fix

**WP-V131-FIND-001 FIXED** — removed unused `os` import; `ruff check src/ tests/` passes locally.

## 9 TypeScript SDK version

**WP-V131-FIND-002 FIXED** — `@responsibleai/client` set to **1.3.1** (was 1.0.0 in tree; Antigravity cited 1.3.0).

## 10 Python package naming

**WP-V131-FIND-003 FIXED (docs)** — `docs/PACKAGE_IDENTITY.md` + README; no PyPI rename.

## 11–13 SDK acceptance

See `WHITEPACT_V131_FINAL_SDK_ACCEPTANCE.md` — Python/TS/Go **PASS** packaging; live-server **DEGRADED**.

## 14 CLI behavioral acceptance

See `WHITEPACT_V131_FINAL_CLI_BEHAVIOR_MATRIX.md` — representative **PASS**; full verb sweep **PARTIAL**.

## 15–17 Regressions

Targeted pytest (24 tests): MCP validation, trust fail-closed, alembic, version — **PASS** locally.

## 18–19 Frontend / a11y

- eslint + vitest (57): **PASS**
- `npm run build`: **PASS** after `npm ci` (Paddle types)
- Customer journey: **CI authoritative** on PR

## 20 Performance

`WHITEPACT_V131_AUTHORITATIVE_PERFORMANCE_REPORT.md` — **29/30** LOCAL in-process p95 &lt; 0.5 ms; `rai_check_trust` network ~100 ms p95.

## 21 Reconciliation

`WHITEPACT_V131_RELEASE_TRUTH_RECONCILIATION.md`

## 22 Migrations

61 files, head **0061** — unchanged.

## 23 Docker / Compose / Helm

Helm **lint PASS**; icon **OPEN P3** (no stable public logo URL committed).

## 24 Full test suite

- **Collected:** 5002 (post-format)
- **Local full run:** long-running; **GitHub Actions authoritative** for this closure
- Do **not** claim local full-suite PASS until log completes

## 25–27 CI / distribution / smoke

Poll PR #114 after push. **Build distribution** required for release-clean verdict.

## 28–31 Findings

| ID | Disposition |
| --- | --- |
| WP-V131-FIND-001 Ruff F401 | **FIXED** |
| WP-V131-FIND-002 TS SDK drift | **FIXED** |
| WP-V131-FIND-003 naming ambiguity | **FIXED** (documentation) |
| WP-V131-FIND-004 Helm icon | **OPEN** (P3 informational) |

## 32–35 Readiness

| Area | Status |
| --- | --- |
| Marketplace technical | **Conditional** on CI + distribution |
| Enterprise pilot | **Conditional** |
| Next action | Merge only after all required CI green + distribution smoke |

---

## Final verdict

**WHITEPACT V1.3.1 RELEASE CLOSURE CONDITIONAL — REMAINING WORK REQUIRED**

Pending: PR #114 **Build distribution** and full required CI matrix green.
